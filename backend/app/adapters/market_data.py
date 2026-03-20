from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

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
    quote_timestamp: datetime | None
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
    def get_setup_data(self, symbol: str) -> SetupMarketData:
        payload = MOCK_MARKET_DATA.get(symbol.upper(), MOCK_MARKET_DATA["AAPL"])
        return SetupMarketData(
            symbol=symbol.upper(),
            provider="mock",
            quote_timestamp=datetime.now(UTC),
            **payload,
        )


class AlpacaPolygonMarketDataAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback = MockMarketDataAdapter()

    def get_setup_data(self, symbol: str) -> SetupMarketData:
        if not self.settings.has_alpaca_credentials:
            return self.fallback.get_setup_data(symbol)
        try:
            with httpx.Client(
                base_url=self.settings.alpaca_data_base_url,
                headers={
                    "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                    "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
                },
                timeout=10.0,
            ) as client:
                latest = client.get(f"/v2/stocks/{symbol.upper()}/quotes/latest")
                latest.raise_for_status()
                quote = latest.json().get("quote", {})
            fallback = self.fallback.get_setup_data(symbol)
            bid = float(quote.get("bp", fallback.bid))
            ask = float(quote.get("ap", fallback.ask))
            return SetupMarketData(
                symbol=symbol.upper(),
                provider="alpaca_quote",
                quote_timestamp=datetime.now(UTC),
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
        except Exception:
            return self.fallback.get_setup_data(symbol)
