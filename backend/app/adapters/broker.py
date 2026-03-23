from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings


@dataclass
class BrokerOrderResult:
    broker_order_id: str | None
    status: str
    payload: dict | None = None


@dataclass
class BrokerEntryOrder:
    symbol: str
    qty: int
    side: str
    order_type: str
    time_in_force: str
    limit_price: float | None = None
    stop_price: float | None = None
    order_class: str = "simple"
    extended_hours: bool = False
    take_profit_limit_price: float | None = None
    stop_loss_stop_price: float | None = None
    stop_loss_limit_price: float | None = None
    reference_price: float | None = None


class BrokerAdapter:
    def place_entry_order(self, order: BrokerEntryOrder) -> BrokerOrderResult:
        raise NotImplementedError

    def place_market_order(self, symbol: str, qty: int, side: str) -> BrokerOrderResult:
        return self.place_entry_order(
            BrokerEntryOrder(
                symbol=symbol, qty=qty, side=side, order_type="market", time_in_force="day"
            )
        )

    def place_stop_order(
        self, symbol: str, qty: int, stop_price: float, side: str = "sell"
    ) -> BrokerOrderResult:
        raise NotImplementedError

    def place_limit_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        side: str = "sell",
        time_in_force: str = "gtc",
        extended_hours: bool = False,
    ) -> BrokerOrderResult:
        raise NotImplementedError

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str, side: str = "sell"
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

    def list_recent_orders(self, limit: int = 50) -> list[dict]:
        raise NotImplementedError

    def get_order(self, broker_order_id: str) -> dict | None:
        raise NotImplementedError

    def get_session_state(self) -> str:
        raise NotImplementedError

    def get_account_summary(self) -> dict[str, float] | None:
        raise NotImplementedError


class PaperBrokerAdapter(BrokerAdapter):
    def __init__(self) -> None:
        self._orders: dict[str, dict] = {}

    def _next_broker_order_id(self) -> str:
        return f"paper-{uuid4().hex[:12]}"

    def _timestamp(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _store_pending_order(self, order: BrokerEntryOrder) -> BrokerOrderResult:
        broker_order_id = self._next_broker_order_id()
        now = self._timestamp()
        payload = {
            "id": broker_order_id,
            "client_order_id": broker_order_id,
            "symbol": order.symbol,
            "qty": str(order.qty),
            "filled_qty": "0",
            "side": order.side,
            "type": order.order_type,
            "time_in_force": order.time_in_force,
            "order_class": order.order_class,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "extended_hours": order.extended_hours,
            "status": "accepted",
            "created_at": now,
            "updated_at": now,
        }
        self._orders[broker_order_id] = payload
        return BrokerOrderResult(broker_order_id=broker_order_id, status="PENDING", payload=payload)

    def _paper_entry_fills_immediately(self, order: BrokerEntryOrder) -> bool:
        if order.order_class != "simple":
            return False
        if order.order_type == "market":
            return True
        if order.order_type == "limit":
            if order.limit_price is None or order.reference_price is None:
                return False
            if order.side == "sell":
                return order.limit_price <= order.reference_price
            return order.limit_price >= order.reference_price
        return False

    def place_entry_order(self, order: BrokerEntryOrder) -> BrokerOrderResult:
        if self._paper_entry_fills_immediately(order):
            return BrokerOrderResult(
                broker_order_id=None,
                status="FILLED",
                payload={
                    "symbol": order.symbol,
                    "qty": str(order.qty),
                    "side": order.side,
                    "type": order.order_type,
                    "time_in_force": order.time_in_force,
                    "order_class": order.order_class,
                    "limit_price": order.limit_price,
                    "stop_price": order.stop_price,
                    "extended_hours": order.extended_hours,
                    "status": "filled",
                },
            )
        if order.order_type in {"limit", "stop", "stop_limit"} or order.order_class in {
            "bracket",
            "oco",
            "oto",
        }:
            return self._store_pending_order(order)
        return BrokerOrderResult(
            broker_order_id=None,
            status="FILLED",
            payload={
                "symbol": order.symbol,
                "qty": str(order.qty),
                "side": order.side,
                "type": order.order_type,
                "time_in_force": order.time_in_force,
                "order_class": order.order_class,
                "limit_price": order.limit_price,
                "stop_price": order.stop_price,
                "extended_hours": order.extended_hours,
                "status": "filled",
            },
        )

    def place_market_order(self, symbol: str, qty: int, side: str) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="FILLED")

    def place_stop_order(
        self, symbol: str, qty: int, stop_price: float, side: str = "sell"
    ) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="ACTIVE")

    def place_limit_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        side: str = "sell",
        time_in_force: str = "gtc",
        extended_hours: bool = False,
    ) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="FILLED")

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str, side: str = "sell"
    ) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="ACTIVE")

    def close_position(self, symbol: str) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id=None, status="FILLED")

    def wait_for_position(
        self, symbol: str, min_qty: int = 1, timeout_seconds: float = 15.0
    ) -> int:
        return min_qty

    def cancel_order(self, broker_order_id: str) -> None:
        payload = self._orders.get(broker_order_id)
        if payload is not None:
            payload["status"] = "canceled"
            payload["updated_at"] = self._timestamp()
        return None

    def list_recent_orders(self, limit: int = 50) -> list[dict]:
        rows = sorted(
            self._orders.values(),
            key=lambda payload: payload.get("updated_at") or payload.get("created_at") or "",
            reverse=True,
        )
        return [dict(order) for order in rows[:limit]]

    def get_order(self, broker_order_id: str) -> dict | None:
        payload = self._orders.get(broker_order_id)
        return dict(payload) if payload is not None else None

    def get_session_state(self) -> str:
        return "regular_open"

    def get_account_summary(self) -> dict[str, float] | None:
        return None


class AlpacaBrokerAdapter(BrokerAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = (
            settings.alpaca_live_api_base_url
            if settings.broker_mode == "alpaca_live"
            else settings.alpaca_api_base_url
        )
        self.market_tz = ZoneInfo("America/New_York")
        self._account_summary_cache: tuple[float, dict[str, float]] | None = None
        self._recent_orders_cache: tuple[float, int, list[dict]] | None = None

    def _client(self) -> httpx.Client:
        self._ensure_execution_allowed()
        return httpx.Client(
            base_url=self.base_url,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
                "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret_key,
            },
            timeout=4.0,
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

    def place_entry_order(self, order: BrokerEntryOrder) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "FILLED", "Alpaca paper credentials are missing for broker execution"
            )
        payload: dict[str, object] = {
            "symbol": order.symbol,
            "qty": order.qty,
            "side": order.side,
            "type": order.order_type,
            "time_in_force": order.time_in_force,
        }
        if order.limit_price is not None:
            payload["limit_price"] = order.limit_price
        if order.stop_price is not None:
            payload["stop_price"] = order.stop_price
        if order.order_class != "simple":
            payload["order_class"] = order.order_class
        if order.extended_hours:
            payload["extended_hours"] = True
        if order.take_profit_limit_price is not None:
            payload["take_profit"] = {"limit_price": order.take_profit_limit_price}
        if order.stop_loss_stop_price is not None:
            stop_loss: dict[str, float] = {"stop_price": order.stop_loss_stop_price}
            if order.stop_loss_limit_price is not None:
                stop_loss["limit_price"] = order.stop_loss_limit_price
            payload["stop_loss"] = stop_loss
        try:
            with self._client() as client:
                response = client.post("/v2/orders", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return self._fallback_or_raise(
                "FILLED", self._extract_http_error_message("Alpaca market order failed", exc)
            )
        return BrokerOrderResult(data.get("id"), str(data.get("status", "accepted")).upper(), data)

    def place_market_order(
        self, symbol: str, qty: int, side: str, time_in_force: str = "day"
    ) -> BrokerOrderResult:
        return self.place_entry_order(
            BrokerEntryOrder(
                symbol=symbol, qty=qty, side=side, order_type="market", time_in_force=time_in_force
            )
        )

    def place_stop_order(
        self, symbol: str, qty: int, stop_price: float, side: str = "sell"
    ) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "ACTIVE", "Alpaca paper credentials are missing for stop execution"
            )
        result = self.place_entry_order(
            BrokerEntryOrder(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type="stop",
                stop_price=stop_price,
                time_in_force="gtc",
            )
        )
        return BrokerOrderResult(result.broker_order_id, result.status, result.payload)

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
        return self.place_entry_order(
            BrokerEntryOrder(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type="limit",
                limit_price=limit_price,
                time_in_force=time_in_force,
                extended_hours=extended_hours,
            )
        )

    def place_trailing_stop(
        self, symbol: str, qty: int, trail: float, trail_unit: str, side: str = "sell"
    ) -> BrokerOrderResult:
        if not self.settings.has_alpaca_credentials:
            return self._fallback_or_raise(
                "ACTIVE", "Alpaca paper credentials are missing for runner execution"
            )
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
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

    def list_recent_orders(self, limit: int = 50) -> list[dict]:
        import time

        cache_entry = self._recent_orders_cache
        if cache_entry is not None:
            cached_at, cached_limit, cached_payload = cache_entry
            if cached_limit >= limit and time.monotonic() - cached_at < 2.0:
                return [dict(order) for order in cached_payload[:limit]]
        if not self.settings.has_alpaca_credentials:
            if self.settings.allow_controller_mock:
                return []
            raise ValueError("Alpaca paper credentials are missing for broker order lookup")
        try:
            with self._client() as client:
                response = client.get(
                    "/v2/orders", params={"status": "all", "direction": "desc", "limit": limit}
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            if self.settings.allow_controller_mock:
                return []
            raise ValueError(
                self._extract_http_error_message("Alpaca recent orders lookup failed", exc)
            ) from exc
        rows = [dict(order) for order in payload] if isinstance(payload, list) else []
        self._recent_orders_cache = (time.monotonic(), limit, rows)
        return [dict(order) for order in rows]

    def get_order(self, broker_order_id: str) -> dict | None:
        if not broker_order_id:
            return None
        if not self.settings.has_alpaca_credentials:
            if self.settings.allow_controller_mock:
                return None
            raise ValueError("Alpaca paper credentials are missing for broker order lookup")
        try:
            with self._client() as client:
                response = client.get(f"/v2/orders/{broker_order_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            if self.settings.allow_controller_mock:
                return None
            raise ValueError(
                self._extract_http_error_message("Alpaca order lookup failed", exc)
            ) from exc
        return payload if isinstance(payload, dict) else None

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

    def get_account_summary(self) -> dict[str, float] | None:
        import time

        cache_entry = self._account_summary_cache
        if cache_entry is not None:
            cached_at, payload = cache_entry
            if time.monotonic() - cached_at < 5.0:
                return dict(payload)
        if not self.settings.has_alpaca_credentials:
            if self.settings.allow_controller_mock:
                return None
            raise ValueError("Alpaca paper credentials are missing for broker account lookup")
        try:
            with self._client() as client:
                response = client.get("/v2/account")
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            if self.settings.allow_controller_mock:
                return None
            raise ValueError(
                self._extract_http_error_message("Alpaca account lookup failed", exc)
            ) from exc
        try:
            equity = float(payload.get("equity") or 0.0)
            buying_power = float(payload.get("buying_power") or 0.0)
            cash = float(payload.get("cash") or 0.0)
        except (TypeError, ValueError):
            return None
        if equity <= 0 or buying_power <= 0:
            return None
        summary = {"equity": equity, "buying_power": buying_power, "cash": cash}
        self._account_summary_cache = (time.monotonic(), summary)
        return dict(summary)
