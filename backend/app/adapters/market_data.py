from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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
    def get_setup_data(self, symbol: str, fallback_reason: str | None = None) -> SetupMarketData:
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
            **payload,
        )


class AlpacaPolygonMarketDataAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback = MockMarketDataAdapter()
        self._market_tz = ZoneInfo("America/New_York")

    def _data_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.alpaca_data_base_url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
            },
            timeout=10.0,
        )

    def _trading_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.alpaca_api_base_url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
            },
            timeout=10.0,
        )

    def _fail_or_fallback(self, symbol: str, reason: str, message: str) -> SetupMarketData:
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

    def _session_state_from_clock(self, clock_payload: dict | None) -> str:
        if not clock_payload:
            return self._session_state_from_timestamp(datetime.now(UTC))
        if bool(clock_payload.get("is_open")):
            return "regular_open"
        current = self._parse_quote_timestamp(str(clock_payload.get("timestamp") or "")) or datetime.now(UTC)
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

    def _latest_quote(self, client: httpx.Client, symbol: str) -> tuple[dict | None, datetime | None]:
        response = client.get(f"/v2/stocks/{symbol}/quotes/latest")
        response.raise_for_status()
        quote = response.json().get("quote")
        if not isinstance(quote, dict):
            return None, None
        return quote, self._parse_quote_timestamp(str(quote.get("t") or ""))

    def _snapshot_quote(self, client: httpx.Client, symbol: str) -> tuple[dict | None, datetime | None]:
        response = client.get(f"/v2/stocks/{symbol}/snapshot")
        response.raise_for_status()
        quote = response.json().get("latestQuote")
        if not isinstance(quote, dict):
            return None, None
        return quote, self._parse_quote_timestamp(str(quote.get("t") or ""))

    def _historical_quote(self, client: httpx.Client, symbol: str) -> tuple[dict | None, datetime | None]:
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

    def _market_clock(self) -> dict | None:
        try:
            with self._trading_client() as client:
                response = client.get("/v2/clock")
                response.raise_for_status()
                payload = response.json()
            return payload if isinstance(payload, dict) else None
        except httpx.HTTPError:
            return None

    def get_setup_data(self, symbol: str) -> SetupMarketData:
        if not self.settings.has_alpaca_credentials:
            return self._fail_or_fallback(
                symbol,
                reason="alpaca_credentials_missing",
                message="Alpaca paper credentials are missing for latest quote retrieval.",
            )
        try:
            quote: dict | None = None
            quote_timestamp: datetime | None = None
            quote_state = "quote_unavailable"
            session_state = "closed"
            with self._data_client() as client:
                latest_quote, latest_timestamp = self._latest_quote(client, symbol.upper())
                if self._has_usable_bid_ask(latest_quote):
                    quote = latest_quote
                    quote_timestamp = latest_timestamp
                    quote_state = "live_quote"
                else:
                    snapshot_quote, snapshot_timestamp = self._snapshot_quote(client, symbol.upper())
                    if self._has_usable_bid_ask(snapshot_quote):
                        quote = snapshot_quote
                        quote_timestamp = snapshot_timestamp
                        quote_state = "cached_quote"
                    else:
                        historical_quote, historical_timestamp = self._historical_quote(client, symbol.upper())
                        if self._has_usable_bid_ask(historical_quote):
                            quote = historical_quote
                            quote_timestamp = historical_timestamp
                            quote_state = "cached_quote"
            clock_payload = self._market_clock()
            session_state = self._session_state_from_clock(clock_payload)
            if session_state != "regular_open" and quote_state == "live_quote":
                quote_state = "cached_quote"
            if not quote:
                raise ValueError(f"Alpaca quote unavailable for {symbol.upper()} right now.")
            fallback = self.fallback.get_setup_data(symbol)
            bid = float(quote.get("bp", fallback.bid))
            ask = float(quote.get("ap", fallback.ask))
            return SetupMarketData(
                symbol=symbol.upper(),
                provider="alpaca_quote",
                provider_state="real_quote_fallback_technicals",
                quote_provider="alpaca",
                technicals_provider="mock",
                quote_is_real=True,
                technicals_are_fallback=True,
                fallback_reason="technicals_fallback_only",
                quote_timestamp=quote_timestamp,
                session_state=session_state,
                quote_state=quote_state,
                bid=bid,
                ask=ask,
                last=round((bid + ask) / 2, 2),
                lod=fallback.lod,
                hod=fallback.hod,
                prev_close=fallback.prev_close,
                atr14=fallback.atr14,
                sma10=fallback.sma10,
                sma50=fallback.sma50,
                sma200=fallback.sma200,
                sma200_prev=fallback.sma200_prev,
                rvol=fallback.rvol,
                days_to_cover=fallback.days_to_cover,
            )
        except Exception as exc:
            return self._fail_or_fallback(
                symbol,
                reason="alpaca_quote_unavailable",
                message=f"Alpaca quote unavailable for {symbol.upper()} right now: {exc}",
            )
