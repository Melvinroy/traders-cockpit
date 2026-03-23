from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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

    def wait_for_position(
        self, symbol: str, min_qty: int = 1, timeout_seconds: float = 15.0
    ) -> int:
        raise NotImplementedError

    def cancel_order(self, broker_order_id: str) -> None:
        raise NotImplementedError

    def get_session_state(self) -> str:
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

    def wait_for_position(
        self, symbol: str, min_qty: int = 1, timeout_seconds: float = 15.0
    ) -> int:
        return min_qty

    def cancel_order(self, broker_order_id: str) -> None:
        return None

    def get_session_state(self) -> str:
        return "regular_open"


class AlpacaBrokerAdapter(BrokerAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = (
            settings.alpaca_live_api_base_url
            if settings.broker_mode == "alpaca_live"
            else settings.alpaca_api_base_url
        )
        self.market_tz = ZoneInfo("America/New_York")

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

    def _extract_http_error_message(self, prefix: str, exc: httpx.HTTPError) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                payload = exc.response.json()
            except ValueError:
                payload = None
            detail = payload.get("message") if isinstance(payload, dict) else exc.response.text
            if detail:
                return f"{prefix}: {detail}"
        return f"{prefix}: {exc}"

    def _parse_timestamp(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _session_state_from_timestamp(self, timestamp: datetime) -> str:
        eastern = timestamp.astimezone(self.market_tz)
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

    def place_market_order(
        self, symbol: str, qty: int, side: str, time_in_force: str = "day"
    ) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "FILLED", "Alpaca paper credentials are missing for broker execution"
            )
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": time_in_force,
        }
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise(
                "FILLED", self._extract_http_error_message("Alpaca market order failed", exc)
            )
        return BrokerOrderResult(data.get("id"), str(data.get("status", "accepted")).upper())

    def place_stop_order(self, symbol: str, qty: int, stop_price: float) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "ACTIVE", "Alpaca paper credentials are missing for stop execution"
            )
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
            return self._fallback_or_raise(
                "ACTIVE", self._extract_http_error_message("Alpaca stop order failed", exc)
            )
        return BrokerOrderResult(data.get("id"), str(data.get("status", "new")).upper())

    def place_limit_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        side: str = "sell",
        time_in_force: str = "gtc",
        extended_hours: bool = False,
    ) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "FILLED", "Alpaca paper credentials are missing for profit execution"
            )
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "limit",
            "limit_price": limit_price,
            "time_in_force": time_in_force,
        }
        if extended_hours:
            payload["extended_hours"] = True
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise(
                "FILLED", self._extract_http_error_message("Alpaca limit order failed", exc)
            )
        return BrokerOrderResult(data.get("id"), str(data.get("status", "accepted")).upper())

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str
    ) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "ACTIVE", "Alpaca paper credentials are missing for runner execution"
            )
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
            return self._fallback_or_raise(
                "ACTIVE", self._extract_http_error_message("Alpaca trailing stop failed", exc)
            )
        return BrokerOrderResult(data.get("id"), str(data.get("status", "new")).upper())

    def close_position(self, symbol: str) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "FILLED", "Alpaca paper credentials are missing for flatten execution"
            )
        try:
            with self._client() as client:
                response = client.delete(f"/v2/positions/{symbol}")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise(
                "FILLED", self._extract_http_error_message("Alpaca close position failed", exc)
            )
        return BrokerOrderResult(data.get("id"), "FILLED")

    def wait_for_position(
        self, symbol: str, min_qty: int = 1, timeout_seconds: float = 15.0
    ) -> int:
        if not self.settings.has_alpaca_credentials:
            if self.settings.allow_controller_mock:
                return min_qty
            raise ValueError("Alpaca paper credentials are missing for broker position checks")
        import time

        end_time = time.monotonic() + timeout_seconds
        last_error: str | None = None
        while time.monotonic() < end_time:
            try:
                with self._client() as client:
                    response = client.get(f"/v2/positions/{symbol}")
                    if response.status_code == 404:
                        time.sleep(0.5)
                        continue
                    response.raise_for_status()
                    data = response.json()
                qty = int(float(data.get("qty", 0)))
                if qty >= min_qty:
                    return qty
                last_error = f"Broker position quantity {qty} is below expected {min_qty}"
            except httpx.HTTPError as exc:
                last_error = self._extract_http_error_message("Alpaca position lookup failed", exc)
            time.sleep(0.5)
        raise ValueError(last_error or f"Broker position for {symbol} is not available yet")

    def cancel_order(self, broker_order_id: str) -> None:
        if not broker_order_id:
            return
        if not self.settings.has_alpaca_credentials:
            if self.settings.allow_controller_mock:
                return
            raise ValueError("Alpaca paper credentials are missing for broker order cancellation")
        try:
            with self._client() as client:
                response = client.delete(f"/v2/orders/{broker_order_id}")
                if response.status_code in {404, 422}:
                    return
                response.raise_for_status()
        except httpx.HTTPError as exc:
            if self.settings.allow_controller_mock:
                return
            raise ValueError(
                self._extract_http_error_message("Alpaca order cancellation failed", exc)
            ) from exc

    def get_session_state(self) -> str:
        if not self.settings.has_alpaca_credentials:
            if self.settings.allow_controller_mock:
                return "regular_open"
            raise ValueError("Alpaca paper credentials are missing for broker clock checks")
        try:
            with self._client() as client:
                response = client.get("/v2/clock")
                response.raise_for_status()
                payload = response.json()
            if bool(payload.get("is_open")):
                return "regular_open"
            timestamp = self._parse_timestamp(str(payload.get("timestamp") or ""))
            return self._session_state_from_timestamp(timestamp or datetime.now(UTC))
        except httpx.HTTPError as exc:
            if self.settings.allow_controller_mock:
                return "regular_open"
            raise ValueError(
                self._extract_http_error_message("Alpaca market clock lookup failed", exc)
            ) from exc
