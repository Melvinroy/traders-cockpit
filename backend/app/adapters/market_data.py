from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
import time

import httpx

from app.core.config import Settings

MOCK_MARKET_DATA: dict[str, dict[str, float]] = {
    "AAPL": {
        "bid": 213.85,
        "ask": 213.92,
        "last": 213.88,
        "lod": 210.40,
        "hod": 215.10,
        "prev_close": 212.50,
        "atr14": 3.20,
        "sma10": 211.20,
        "sma50": 198.40,
        "sma200": 195.20,
        "sma200_prev": 194.80,
        "rvol": 1.80,
        "days_to_cover": 2.40,
    },
    "NVDA": {
        "bid": 931.25,
        "ask": 931.95,
        "last": 931.60,
        "lod": 918.10,
        "hod": 938.40,
        "prev_close": 926.50,
        "atr14": 18.40,
        "sma10": 910.80,
        "sma50": 846.40,
        "sma200": 701.10,
        "sma200_prev": 699.80,
        "rvol": 2.65,
        "days_to_cover": 1.25,
    },
}


@dataclass
class SetupMarketData:
    symbol: str
    provider: str
    provider_state: str
    quote_provider: str
    technicals_provider: str
    quote_is_real: bool
    technicals_are_fallback: bool
    fallback_reason: str | None
    quote_timestamp: datetime | None
    session_state: str
    quote_state: str
    entry_basis: str
    bid: float
    ask: float
    last: float
    lod: float
    hod: float
    prev_close: float
    atr14: float
    sma10: float
    sma50: float
    sma200: float
    sma200_prev: float
    rvol: float
    days_to_cover: float


class MockMarketDataAdapter:
    def get_setup_data(
        self, symbol: str, fallback_reason: str | None = None
    ) -> SetupMarketData:
        payload = MOCK_MARKET_DATA.get(symbol.upper(), MOCK_MARKET_DATA["AAPL"])
        return SetupMarketData(
            symbol=symbol.upper(),
            provider="mock",
            provider_state="fallback_all",
            quote_provider="mock",
            technicals_provider="mock",
            quote_is_real=False,
            technicals_are_fallback=True,
            fallback_reason=fallback_reason,
            quote_timestamp=datetime.now(UTC),
            session_state="closed",
            quote_state="quote_unavailable",
            entry_basis="bid_ask_midpoint",
            **payload,
        )


class AlpacaPolygonMarketDataAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback = MockMarketDataAdapter()
        self._market_tz = ZoneInfo("America/New_York")
        self._setup_cache: dict[str, tuple[float, SetupMarketData]] = {}

    def _data_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.alpaca_data_base_url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
            },
            timeout=4.0,
        )

    def _trading_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.alpaca_api_base_url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
            },
            timeout=4.0,
        )

    def _fail_or_fallback(
        self, symbol: str, reason: str, message: str
    ) -> SetupMarketData:
        if self.settings.broker_mode in {"alpaca_paper", "alpaca_live"}:
            raise ValueError(message)
        if self.settings.allow_controller_mock:
            return self.fallback.get_setup_data(symbol, fallback_reason=reason)
        raise ValueError(message)

    def _parse_quote_timestamp(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            value = raw.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _has_usable_bid_ask(self, quote: dict | None) -> bool:
        if not isinstance(quote, dict):
            return False
        try:
            bid = float(quote.get("bp", 0.0) or 0.0)
            ask = float(quote.get("ap", 0.0) or 0.0)
        except (TypeError, ValueError):
            return False
        return bid > 0 and ask > 0

    def _parse_float(self, value: object, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _session_state_from_clock(self, clock_payload: dict | None) -> str:
        if not clock_payload:
            return self._session_state_from_timestamp(datetime.now(UTC))
        if bool(clock_payload.get("is_open")):
            return "regular_open"
        current = self._parse_quote_timestamp(
            str(clock_payload.get("timestamp") or "")
        ) or datetime.now(UTC)
        return self._session_state_from_timestamp(current)

    def _session_state_from_timestamp(self, timestamp: datetime) -> str:
        eastern = timestamp.astimezone(self._market_tz)
        if eastern.weekday() >= 5:
            return "closed"
        current_minutes = eastern.hour * 60 + eastern.minute
        if 570 <= current_minutes < 960:
            return "regular_open"
        if 240 <= current_minutes < 570:
            return "pre_market"
        if 960 <= current_minutes < 1200:
            return "after_hours"
        return "overnight"

    def _latest_quote(
        self, client: httpx.Client, symbol: str
    ) -> tuple[dict | None, datetime | None]:
        response = client.get(f"/v2/stocks/{symbol}/quotes/latest")
        response.raise_for_status()
        quote = response.json().get("quote")
        if not isinstance(quote, dict):
            return None, None
        return quote, self._parse_quote_timestamp(str(quote.get("t") or ""))

    def _snapshot_quote(
        self, client: httpx.Client, symbol: str
    ) -> tuple[dict | None, datetime | None]:
        response = client.get(f"/v2/stocks/{symbol}/snapshot")
        response.raise_for_status()
        quote = response.json().get("latestQuote")
        if not isinstance(quote, dict):
            return None, None
        return quote, self._parse_quote_timestamp(str(quote.get("t") or ""))

    def _snapshot_payload(self, client: httpx.Client, symbol: str) -> dict | None:
        response = client.get(f"/v2/stocks/{symbol}/snapshot")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    def _load_snapshot_payload(self, symbol: str) -> dict | None:
        with self._data_client() as client:
            return self._snapshot_payload(client, symbol)

    def _historical_quote(
        self, client: httpx.Client, symbol: str
    ) -> tuple[dict | None, datetime | None]:
        response = client.get(
            f"/v2/stocks/{symbol}/quotes",
            params={"limit": 1, "sort": "desc", "feed": "iex"},
        )
        response.raise_for_status()
        quotes = response.json().get("quotes")
        if not isinstance(quotes, list) or not quotes:
            return None, None
        quote = quotes[0]
        if not isinstance(quote, dict):
            return None, None
        return quote, self._parse_quote_timestamp(str(quote.get("t") or ""))

    def _daily_bars(
        self, client: httpx.Client, symbol: str, *, limit: int = 60
    ) -> list[dict]:
        end = datetime.now(UTC)
        start = end - timedelta(days=max(limit * 2, 45))
        response = client.get(
            f"/v2/stocks/{symbol}/bars",
            params={
                "timeframe": "1Day",
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": end.isoformat().replace("+00:00", "Z"),
                "limit": max(20, min(limit, 200)),
                "feed": "iex",
                "adjustment": "raw",
            },
        )
        response.raise_for_status()
        rows = response.json().get("bars")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _load_daily_bars(self, symbol: str, *, limit: int = 60) -> list[dict]:
        with self._data_client() as client:
            return self._daily_bars(client, symbol, limit=limit)

    def _atr14(self, bars: list[dict]) -> float | None:
        if len(bars) < 14:
            return None
        true_ranges: list[float] = []
        prev_close: float | None = None
        for bar in bars:
            high = self._parse_float(bar.get("h"))
            low = self._parse_float(bar.get("l"))
            close = self._parse_float(bar.get("c"))
            if min(high, low, close) <= 0:
                continue
            if prev_close is None:
                tr = high - low
            else:
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
            prev_close = close
        if len(true_ranges) < 14:
            return None
        atr = sum(true_ranges[:14]) / 14
        for tr in true_ranges[14:]:
            atr = ((atr * 13) + tr) / 14
        return round(atr, 4)

    def _market_clock(self) -> dict | None:
        try:
            with self._trading_client() as client:
                response = client.get("/v2/clock")
                response.raise_for_status()
                payload = response.json()
            return payload if isinstance(payload, dict) else None
        except httpx.HTTPError:
            return None

    def _cache_ttl(self, session_state: str) -> float:
        return 8.0 if session_state == "regular_open" else 45.0

    def _get_cached_setup(self, symbol: str) -> SetupMarketData | None:
        cache_entry = self._setup_cache.get(symbol.upper())
        if cache_entry is None:
            return None
        cached_at, payload = cache_entry
        if time.monotonic() - cached_at > self._cache_ttl(payload.session_state):
            self._setup_cache.pop(symbol.upper(), None)
            return None
        return SetupMarketData(**payload.__dict__)

    def _store_cached_setup(
        self, symbol: str, payload: SetupMarketData
    ) -> SetupMarketData:
        self._setup_cache[symbol.upper()] = (time.monotonic(), payload)
        return SetupMarketData(**payload.__dict__)

    def get_setup_data(self, symbol: str) -> SetupMarketData:
        cached = self._get_cached_setup(symbol)
        if cached is not None:
            return cached
        if not self.settings.has_alpaca_credentials:
            return self._fail_or_fallback(
                symbol,
                reason="alpaca_credentials_missing",
                message="Alpaca paper credentials are missing for latest quote retrieval.",
            )
        try:
            upper_symbol = symbol.upper()
            with ThreadPoolExecutor(max_workers=3) as executor:
                snapshot_future = executor.submit(
                    self._load_snapshot_payload, upper_symbol
                )
                daily_bars_future = executor.submit(self._load_daily_bars, upper_symbol)
                clock_future = executor.submit(self._market_clock)
                snapshot_payload = snapshot_future.result()
                daily_bars = daily_bars_future.result()
                clock_payload = clock_future.result()
            snapshot_quote = (
                snapshot_payload.get("latestQuote")
                if isinstance(snapshot_payload, dict)
                else None
            )
            latest_trade = (
                snapshot_payload.get("latestTrade")
                if isinstance(snapshot_payload, dict)
                else None
            )
            daily_bar = (
                snapshot_payload.get("dailyBar")
                if isinstance(snapshot_payload, dict)
                else None
            )
            prev_daily_bar = (
                snapshot_payload.get("prevDailyBar")
                if isinstance(snapshot_payload, dict)
                else None
            )
            with self._data_client() as client:
                quote: dict | None = None
                quote_timestamp: datetime | None = None
                quote_state = "quote_unavailable"
                snapshot_timestamp = self._parse_quote_timestamp(
                    str((snapshot_quote or {}).get("t") or "")
                )
                if self._has_usable_bid_ask(snapshot_quote):
                    quote = snapshot_quote
                    quote_timestamp = snapshot_timestamp
                    quote_state = "cached_quote"
                else:
                    latest_quote, latest_timestamp = self._latest_quote(
                        client, symbol.upper()
                    )
                    if self._has_usable_bid_ask(latest_quote):
                        quote = latest_quote
                        quote_timestamp = latest_timestamp
                        quote_state = "live_quote"
                    else:
                        historical_quote, historical_timestamp = self._historical_quote(
                            client, upper_symbol
                        )
                        if isinstance(historical_quote, dict):
                            quote = historical_quote
                            quote_timestamp = historical_timestamp
                            quote_state = "cached_quote"
            session_state = self._session_state_from_clock(clock_payload)
            if session_state != "regular_open" and quote_state == "live_quote":
                quote_state = "cached_quote"
            if not quote:
                raise ValueError(
                    f"Alpaca quote unavailable for {upper_symbol} right now."
                )
            last_trade_price = self._parse_float((latest_trade or {}).get("p"))
            fallback = self.fallback.get_setup_data(symbol)
            bid = self._parse_float(quote.get("bp"))
            ask = self._parse_float(quote.get("ap"))
            if bid <= 0:
                bid = last_trade_price
            if ask <= 0:
                ask = last_trade_price
            if bid <= 0 or ask <= 0:
                raise ValueError(
                    f"Alpaca quote unavailable for {upper_symbol} right now."
                )
            if not isinstance(daily_bar, dict):
                raise ValueError(
                    f"Alpaca daily bar unavailable for {upper_symbol} right now."
                )
            lod = self._parse_float(daily_bar.get("l"))
            hod = self._parse_float(daily_bar.get("h"))
            prev_close = self._parse_float(
                (prev_daily_bar or {}).get("c"), fallback.prev_close
            )
            atr14 = self._atr14(daily_bars)
            if lod <= 0 or hod <= 0:
                raise ValueError(
                    f"Alpaca daily range unavailable for {upper_symbol} right now."
                )
            if atr14 is None or atr14 <= 0:
                raise ValueError(
                    f"Alpaca ATR14 unavailable for {upper_symbol} right now."
                )
            entry_basis = (
                "bid_ask_midpoint"
                if self._parse_float(quote.get("bp")) > 0
                and self._parse_float(quote.get("ap")) > 0
                else "hybrid_quote_trade_midpoint"
            )
            payload = SetupMarketData(
                symbol=upper_symbol,
                provider="alpaca_market",
                provider_state="real_quote_range_atr_fallback_technicals",
                quote_provider="alpaca",
                technicals_provider="mock",
                quote_is_real=True,
                technicals_are_fallback=True,
                fallback_reason="partial_technicals_fallback_only",
                quote_timestamp=quote_timestamp,
                session_state=session_state,
                quote_state=quote_state,
                entry_basis=entry_basis,
                bid=bid,
                ask=ask,
                last=round(
                    last_trade_price if last_trade_price > 0 else (bid + ask) / 2, 2
                ),
                lod=lod,
                hod=hod,
                prev_close=prev_close,
                atr14=atr14,
                sma10=fallback.sma10,
                sma50=fallback.sma50,
                sma200=fallback.sma200,
                sma200_prev=fallback.sma200_prev,
                rvol=fallback.rvol,
                days_to_cover=fallback.days_to_cover,
            )
            return self._store_cached_setup(symbol, payload)
        except Exception as exc:
            return self._fail_or_fallback(
                symbol,
                reason="alpaca_quote_unavailable",
                message=f"Alpaca quote unavailable for {symbol.upper()} right now: {exc}",
            )
