from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass
class BrokerOrderResult:
    broker_order_id: str | None
    status: str


class BrokerAdapter:
    def place_market_order(self, symbol: str, qty: int, side: str) -> BrokerOrderResult:
        raise NotImplementedError

    def place_stop_order(self, symbol: str, qty: int, stop_price: float) -> BrokerOrderResult:
        raise NotImplementedError

    def place_limit_order(self, symbol: str, qty: int, limit_price: float) -> BrokerOrderResult:
        raise NotImplementedError

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str
    ) -> BrokerOrderResult:
        raise NotImplementedError

    def close_position(self, symbol: str) -> BrokerOrderResult:
        raise NotImplementedError


class PaperBrokerAdapter(BrokerAdapter):
    def place_market_order(self, symbol: str, qty: int, side: str) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="FILLED")

    def place_stop_order(self, symbol: str, qty: int, stop_price: float) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="ACTIVE")

    def place_limit_order(self, symbol: str, qty: int, limit_price: float) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="FILLED")

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str
    ) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="ACTIVE")

    def close_position(self, symbol: str) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="FILLED")


class AlpacaBrokerAdapter(BrokerAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = (
            settings.alpaca_live_api_base_url
            if settings.broker_mode == "alpaca_live"
            else settings.alpaca_api_base_url
        )

    def _client(self) -> httpx.Client:
        self._ensure_execution_allowed()
        return httpx.Client(
            base_url=self.base_url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
            },
            timeout=10.0,
        )

    def _ensure_execution_allowed(self) -> None:
        if self.settings.broker_mode != "alpaca_live":
            return
        if not self.settings.allow_live_trading:
            raise ValueError("Live trading is disabled by config")
        if not self.settings.live_confirmation_token:
            raise ValueError("Live trading confirmation token is not configured")

    def _fallback_or_raise(self, fallback_status: str, message: str) -> BrokerOrderResult:
        if self.settings.allow_controller_mock:
            return BrokerOrderResult(None, fallback_status)
        raise ValueError(message)

    def place_market_order(self, symbol: str, qty: int, side: str) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise("FILLED", "Alpaca paper credentials are missing for broker execution")
        payload = {"symbol": symbol, "qty": qty, "side": side, "type": "market", "time_in_force": "day"}
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise("FILLED", f"Alpaca market order failed: {exc}")
        return BrokerOrderResult(data.get("id"), str(data.get("status", "accepted")).upper())

    def place_stop_order(self, symbol: str, qty: int, stop_price: float) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise("ACTIVE", "Alpaca paper credentials are missing for stop execution")
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": "sell",
            "type": "stop",
            "stop_price": stop_price,
            "time_in_force": "gtc",
        }
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise("ACTIVE", f"Alpaca stop order failed: {exc}")
        return BrokerOrderResult(data.get("id"), str(data.get("status", "new")).upper())

    def place_limit_order(self, symbol: str, qty: int, limit_price: float) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise("FILLED", "Alpaca paper credentials are missing for profit execution")
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": "sell",
            "type": "limit",
            "limit_price": limit_price,
            "time_in_force": "gtc",
        }
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise("FILLED", f"Alpaca limit order failed: {exc}")
        return BrokerOrderResult(data.get("id"), str(data.get("status", "accepted")).upper())

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str
    ) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise("ACTIVE", "Alpaca paper credentials are missing for runner execution")
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": "sell",
            "type": "trailing_stop",
            "time_in_force": "gtc",
        }
        if trail_unit == "$":
            payload["trail_price"] = trail
        else:
            payload["trail_percent"] = trail
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise("ACTIVE", f"Alpaca trailing stop failed: {exc}")
        return BrokerOrderResult(data.get("id"), str(data.get("status", "new")).upper())

    def close_position(self, symbol: str) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise("FILLED", "Alpaca paper credentials are missing for flatten execution")
        try:
            with self._client() as client:
                response = client.delete(f"/v2/positions/{symbol}")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise("FILLED", f"Alpaca close position failed: {exc}")
        return BrokerOrderResult(data.get("id"), "FILLED")
