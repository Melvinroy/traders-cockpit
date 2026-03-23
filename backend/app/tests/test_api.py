from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

db_path = Path(__file__).resolve().parent / "test.db"
if db_path.exists():
    db_path.unlink()
auth_db_path = Path(__file__).resolve().parent / "auth-test.db"
if auth_db_path.exists():
    auth_db_path.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["AUTH_STORAGE_MODE"] = "file"
os.environ["AUTH_DB_PATH"] = str(auth_db_path)
os.environ["AUTH_REQUIRE_LOGIN"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.adapters.broker import AlpacaBrokerAdapter, BrokerEntryOrder  # noqa: E402
from app.adapters.market_data import AlpacaPolygonMarketDataAdapter, SetupMarketData  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app, service  # noqa: E402
from app.models.entities import (  # noqa: E402
    AccountSettingsEntity,
    OrderEntity,
    PositionEntity,
    TradeLogEntity,
)
from app.schemas.cockpit import TrancheMode  # noqa: E402
from app.services.auth import FAILED_LOGIN_LIMIT, get_auth_store  # noqa: E402
from app.core.config import Settings, _normalize_database_url  # noqa: E402
from app.core.observability import (  # noqa: E402
    REQUEST_ID_HEADER,
    bind_request_id,
    reset_request_id,
)
from app.api import deps_auth  # noqa: E402
from app import main as main_module  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)
auth_store = get_auth_store(Settings.from_env())
auth_store.bootstrap_users(
    admin_username="admin",
    admin_password="change-me-admin",
    trader_username="trader",
    trader_password="change-me-trader",
    seed_enabled=True,
)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    with SessionLocal() as db:
        db.query(OrderEntity).delete()
        db.query(PositionEntity).delete()
        db.query(TradeLogEntity).delete()
        db.commit()
    auth_store.reset_for_tests()
    auth_store.bootstrap_users(
        admin_username="admin",
        admin_password="change-me-admin",
        trader_username="trader",
        trader_password="change-me-trader",
        seed_enabled=True,
    )
    yield


def tranche_modes() -> list[dict]:
    return [
        {
            "mode": "limit",
            "allocationPct": 33.33,
            "trail": 2,
            "trailUnit": "$",
            "target": "1R",
            "manualPrice": None,
        },
        {
            "mode": "limit",
            "allocationPct": 33.33,
            "trail": 2,
            "trailUnit": "$",
            "target": "2R",
            "manualPrice": None,
        },
        {
            "mode": "runner",
            "allocationPct": 33.34,
            "trail": 2,
            "trailUnit": "$",
            "target": "3R",
            "manualPrice": None,
        },
    ]


def simple_entry_order(side: str = "buy", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "side": side,
        "orderType": "limit",
        "timeInForce": "day",
        "orderClass": "simple",
        "extendedHours": False,
        "limitPrice": None,
        "stopPrice": None,
        "otoExitSide": "stop_loss",
        "takeProfit": None,
        "stopLoss": None,
    }
    payload.update(overrides)
    return payload


def structured_events(caplog: pytest.LogCaptureFixture) -> list[dict]:
    events: list[dict] = []
    for record in caplog.records:
        if record.name != "traders_cockpit":
            continue
        try:
            events.append(json.loads(record.getMessage()))
        except json.JSONDecodeError:
            continue
    return events


def test_setup_endpoint_returns_contract() -> None:
    response = client.get("/api/setup/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["provider"] in {"mock", "alpaca_quote"}
    assert data["providerState"]
    assert data["quoteProvider"]
    assert data["technicalsProvider"]
    assert data["executionProvider"] == "paper"
    assert data["sessionState"]
    assert data["quoteState"]
    assert isinstance(data["quoteIsReal"], bool)
    assert isinstance(data["technicalsAreFallback"], bool)
    assert data["entryBasis"] == "bid_ask_midpoint"
    assert data["stopReferenceDefault"] in {"lod", "atr", "manual"}
    assert isinstance(data["lodIsValid"], bool)
    assert isinstance(data["atrIsValid"], bool)
    assert "equitySource" in data
    if data["stopReferenceDefault"] != "manual":
        assert data["entry"] > data["finalStop"]
        assert data["shares"] >= 0


def test_health_live_returns_liveness_contract() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["kind"] == "live"
    assert "broker_mode" in payload


def test_health_ready_returns_readiness_contract() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["kind"] == "ready"
    assert payload["runtime_contract"]["status"] == "ok"
    assert "dependencies" in payload


def test_health_ready_returns_503_when_readiness_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module,
        "build_readiness_report",
        lambda settings: {
            "status": "error",
            "kind": "ready",
            "app_env": settings.app_env,
            "broker_mode": settings.broker_mode,
            "runtime_contract": {
                "status": "error",
                "issues": ["forced readiness failure"],
            },
            "dependencies": {"auth": {"status": "error", "detail": "forced"}},
        },
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_request_id_header_is_generated_and_reused() -> None:
    generated = client.get("/health")
    assert generated.status_code == 200
    generated_request_id = generated.headers.get(REQUEST_ID_HEADER)
    assert generated_request_id

    echoed = client.get("/health", headers={REQUEST_ID_HEADER: "req-health-123"})
    assert echoed.status_code == 200
    assert echoed.headers.get(REQUEST_ID_HEADER) == "req-health-123"


def test_request_completion_logs_include_request_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="traders_cockpit")

    response = client.get("/health", headers={REQUEST_ID_HEADER: "req-health-log-1"})

    assert response.status_code == 200
    events = structured_events(caplog)
    request_event = next(
        event for event in events if event.get("event") == "http.request.completed"
    )
    assert request_event["request_id"] == "req-health-log-1"
    assert request_event["method"] == "GET"
    assert request_event["path"] == "/health"
    assert request_event["status"] == 200
    assert isinstance(request_event["duration_ms"], float | int)


def test_websocket_auth_failure_logs_request_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    previous = deps_auth.settings.auth_require_login
    deps_auth.settings.auth_require_login = True
    caplog.set_level(logging.INFO, logger="traders_cockpit")
    try:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/cockpit?request_id=req-ws-auth-fail&client_session_id=ws-client-auth-fail"
            ) as websocket:
                websocket.receive_text()
    finally:
        deps_auth.settings.auth_require_login = previous

    events = structured_events(caplog)
    auth_event = next(event for event in events if event.get("event") == "ws.auth.failed")
    assert auth_event["request_id"] == "req-ws-auth-fail"
    assert auth_event["client_session_id"] == "ws-client-auth-fail"
    assert auth_event["path"] == "/ws/cockpit"


def test_postgres_urls_normalize_to_psycopg_driver() -> None:
    assert (
        _normalize_database_url("postgresql://user:pass@host:5432/dbname")
        == "postgresql+psycopg://user:pass@host:5432/dbname"
    )
    assert (
        _normalize_database_url("postgresql+psycopg://user:pass@host:5432/dbname")
        == "postgresql+psycopg://user:pass@host:5432/dbname"
    )
    assert _normalize_database_url("sqlite:///./data/test.db") == "sqlite:///./data/test.db"


def test_local_personal_paper_ready_requires_real_alpaca_creds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BROKER_MODE", "alpaca_paper")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "false")
    monkeypatch.setenv("ALPACA_API_KEY_ID", "paper-key")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "paper-secret")
    assert Settings.from_env().local_personal_paper_ready is True

    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)
    assert Settings.from_env().local_personal_paper_ready is False


def test_alpaca_market_order_fails_loudly_without_mock_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BROKER_MODE", "alpaca_paper")
    monkeypatch.setenv("ALLOW_CONTROLLER_MOCK", "false")
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)

    adapter = AlpacaBrokerAdapter(Settings.from_env())
    with pytest.raises(ValueError, match="credentials are missing"):
        adapter.place_market_order("MSFT", 10, "buy")


def test_alpaca_entry_fallback_logs_structured_event(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("BROKER_MODE", "alpaca_paper")
    monkeypatch.setenv("ALLOW_CONTROLLER_MOCK", "true")
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)

    adapter = AlpacaBrokerAdapter(Settings.from_env())
    caplog.set_level(logging.INFO, logger="traders_cockpit")
    token = bind_request_id("req-broker-fallback-1")
    try:
        result = adapter.place_entry_order(
            BrokerEntryOrder(
                symbol="MSFT",
                qty=10,
                side="buy",
                order_type="limit",
                time_in_force="day",
                limit_price=380.5,
            )
        )
    finally:
        reset_request_id(token)

    assert result.status == "FILLED"
    events = structured_events(caplog)
    fallback_event = next(
        event for event in events if event.get("event") == "broker.entry.submit.fallback"
    )
    assert fallback_event["request_id"] == "req-broker-fallback-1"
    assert fallback_event["symbol"] == "MSFT"
    assert fallback_event["order_type"] == "limit"
    assert fallback_event["fallback_status"] == "FILLED"
    assert fallback_event["outcome"] == "fallback"


def test_market_data_fallback_logs_structured_event(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("BROKER_MODE", "alpaca_paper")
    monkeypatch.setenv("ALLOW_CONTROLLER_MOCK", "true")
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)

    adapter = AlpacaPolygonMarketDataAdapter(Settings.from_env())
    caplog.set_level(logging.INFO, logger="traders_cockpit")
    token = bind_request_id("req-market-fallback-1")
    try:
        payload = adapter.get_setup_data("MSFT")
    finally:
        reset_request_id(token)

    assert payload.provider == "mock"
    events = structured_events(caplog)
    fallback_event = next(
        event for event in events if event.get("event") == "market_data.setup.fallback"
    )
    assert fallback_event["request_id"] == "req-market-fallback-1"
    assert fallback_event["symbol"] == "MSFT"
    assert fallback_event["reason"] == "alpaca_credentials_missing"
    assert fallback_event["outcome"] == "fallback"


def test_wait_for_position_logs_retry_and_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import time

    monkeypatch.setenv("BROKER_MODE", "alpaca_paper")
    monkeypatch.setenv("ALLOW_CONTROLLER_MOCK", "false")
    monkeypatch.setenv("ALPACA_API_KEY_ID", "paper-key")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "paper-secret")

    adapter = AlpacaBrokerAdapter(Settings.from_env())
    caplog.set_level(logging.INFO, logger="traders_cockpit")
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    responses = [
        httpx.Response(404, request=httpx.Request("GET", "https://example.test/v2/positions/MSFT")),
        httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.test/v2/positions/MSFT"),
            json={"qty": "5"},
        ),
    ]

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, _url: str):
            return responses.pop(0)

    monkeypatch.setattr(adapter, "_client", lambda: FakeClient())
    token = bind_request_id("req-wait-1")
    try:
        qty = adapter.wait_for_position("MSFT", min_qty=5, timeout_seconds=1.0)
    finally:
        reset_request_id(token)

    assert qty == 5
    events = structured_events(caplog)
    retry_event = next(
        event for event in events if event.get("event") == "broker.position.wait.retry"
    )
    success_event = next(
        event for event in events if event.get("event") == "broker.position.wait.succeeded"
    )
    assert retry_event["request_id"] == "req-wait-1"
    assert retry_event["symbol"] == "MSFT"
    assert retry_event["attempt"] == 1
    assert retry_event["outcome"] == "retry"
    assert success_event["request_id"] == "req-wait-1"
    assert success_event["symbol"] == "MSFT"
    assert success_event["qty"] == 5
    assert success_event["attempts"] == 2
    assert success_event["outcome"] == "success"


def test_setup_fails_loudly_when_real_quote_is_unavailable() -> None:
    original_allow_mock = service.settings.allow_controller_mock
    original_get_setup_data = service.market_data.get_setup_data
    service.settings.allow_controller_mock = False

    def fail_quote(_symbol: str):
        raise ValueError("Latest Alpaca quote is unavailable for MSFT")

    service.market_data.get_setup_data = fail_quote
    try:
        response = client.get("/api/setup/MSFT")
        assert response.status_code == 400
        assert "Latest Alpaca quote is unavailable" in response.text
    finally:
        service.settings.allow_controller_mock = original_allow_mock
        service.market_data.get_setup_data = original_get_setup_data


def test_build_setup_defaults_to_manual_when_real_lod_is_invalid() -> None:
    market = SetupMarketData(
        symbol="AAPL",
        provider="alpaca_market",
        provider_state="real_quote_range_atr_fallback_technicals",
        quote_provider="alpaca",
        technicals_provider="mock",
        quote_is_real=True,
        technicals_are_fallback=True,
        fallback_reason="partial_technicals_fallback_only",
        quote_timestamp=None,
        session_state="after_hours",
        quote_state="cached_quote",
        entry_basis="bid_ask_midpoint",
        bid=101.00,
        ask=101.20,
        last=101.10,
        lod=101.50,
        hod=103.00,
        prev_close=100.00,
        atr14=2.25,
        sma10=100.0,
        sma50=95.0,
        sma200=90.0,
        sma200_prev=89.5,
        rvol=1.2,
        days_to_cover=2.0,
    )
    setup = service._build_setup_response(market, 50000.0, 200000.0, 1.0, "alpaca_account", 15000.0)
    assert setup.stopReferenceDefault == "manual"
    assert setup.lodIsValid is False
    assert setup.manualStopWarning
    assert setup.shares == 0
    assert setup.finalStop == 0.0


def test_build_setup_uses_real_lod_when_valid() -> None:
    market = SetupMarketData(
        symbol="AAPL",
        provider="alpaca_market",
        provider_state="real_quote_range_atr_fallback_technicals",
        quote_provider="alpaca",
        technicals_provider="mock",
        quote_is_real=True,
        technicals_are_fallback=True,
        fallback_reason="partial_technicals_fallback_only",
        quote_timestamp=None,
        session_state="regular_open",
        quote_state="live_quote",
        entry_basis="bid_ask_midpoint",
        bid=101.00,
        ask=101.20,
        last=101.10,
        lod=98.00,
        hod=103.00,
        prev_close=100.00,
        atr14=2.25,
        sma10=100.0,
        sma50=95.0,
        sma200=90.0,
        sma200_prev=89.5,
        rvol=1.2,
        days_to_cover=2.0,
    )
    setup = service._build_setup_response(market, 50000.0, 200000.0, 1.0, "alpaca_account", 15000.0)
    assert setup.stopReferenceDefault == "lod"
    assert setup.lodIsValid is True
    assert setup.finalStop == 98.0
    assert setup.atrStop == round(setup.entry - market.atr14, 2)
    assert setup.shares > 0


def test_get_account_uses_broker_equity_for_alpaca_paper_mode() -> None:
    original_broker = service.broker
    original_mode = service.settings.broker_mode

    class StubBroker:
        def get_account_summary(self) -> dict[str, float]:
            return {"equity": 76543.21, "buying_power": 123456.78, "cash": 10000.0}

    service.broker = StubBroker()
    service.settings.broker_mode = "alpaca_paper"
    try:
        with SessionLocal() as db:
            service.ensure_seed_data(db)
            settings_row = db.scalar(select(AccountSettingsEntity))
            assert settings_row is not None
            settings_row.mode = "alpaca_paper"
            db.commit()
            account = service.get_account(db)
        assert account.equity == 76543.21
        assert account.buying_power == 123456.78
        assert account.cash == 10000.0
        assert account.equity_source == "alpaca_account"
    finally:
        service.broker = original_broker
        service.settings.broker_mode = original_mode


def test_split_shares_uses_allocation_percentages() -> None:
    allocations = [
        {
            "mode": "limit",
            "allocationPct": 50.0,
            "trail": 2,
            "trailUnit": "$",
            "target": "1R",
            "manualPrice": None,
        },
        {
            "mode": "limit",
            "allocationPct": 30.0,
            "trail": 2,
            "trailUnit": "$",
            "target": "2R",
            "manualPrice": None,
        },
        {
            "mode": "runner",
            "allocationPct": 20.0,
            "trail": 2,
            "trailUnit": "$",
            "target": "3R",
            "manualPrice": None,
        },
    ]
    result = service._split_shares(
        101, 3, [TrancheMode.model_validate(item) for item in allocations]
    )
    assert result == [51, 30, 20]


def test_login_creates_session_and_me_resolves_user() -> None:
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "change-me-admin"}
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"
    assert payload["expires_at"]
    assert "set-cookie" in login.headers

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    after = client.get("/api/auth/me")
    assert after.status_code == 401


def test_auth_login_failure_logs_request_scoped_event(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="traders_cockpit")

    response = client.post(
        "/api/auth/login",
        headers={REQUEST_ID_HEADER: "req-auth-fail-1"},
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers.get(REQUEST_ID_HEADER) == "req-auth-fail-1"
    events = structured_events(caplog)
    login_failure = next(event for event in events if event.get("event") == "auth.login.failed")
    assert login_failure["request_id"] == "req-auth-fail-1"
    assert login_failure["username"] == "admin"
    assert "password" not in json.dumps(login_failure)


def test_login_rate_limits_repeated_failures() -> None:
    for _ in range(FAILED_LOGIN_LIMIT):
        failed = client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong-password"}
        )
        assert failed.status_code == 401

    blocked = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert blocked.status_code == 429
    assert "Too many login attempts" in blocked.json()["detail"]

    success = client.post(
        "/api/auth/login", json={"username": "admin", "password": "change-me-admin"}
    )
    assert success.status_code == 429


def test_successful_login_before_limit_clears_failures() -> None:
    for _ in range(FAILED_LOGIN_LIMIT - 1):
        failed = client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong-password"}
        )
        assert failed.status_code == 401

    success = client.post(
        "/api/auth/login", json={"username": "admin", "password": "change-me-admin"}
    )
    assert success.status_code == 200

    follow_up_failure = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert follow_up_failure.status_code == 401


def test_staging_cookie_settings_can_support_hosted_preview() -> None:
    import app.api.routes_auth as routes_auth_module

    original_samesite = routes_auth_module.settings.auth_cookie_samesite
    original_secure = routes_auth_module.settings.auth_cookie_secure
    routes_auth_module.settings.auth_cookie_samesite = "none"
    routes_auth_module.settings.auth_cookie_secure = True
    try:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "change-me-admin"}
        )
        assert login.status_code == 200
        cookie_header = login.headers.get("set-cookie", "").lower()
        assert "samesite=none" in cookie_header
        assert "secure" in cookie_header
    finally:
        routes_auth_module.settings.auth_cookie_samesite = original_samesite
        routes_auth_module.settings.auth_cookie_secure = original_secure
        client.post("/api/auth/logout")


def test_sensitive_routes_require_session_when_auth_is_enabled() -> None:
    previous = deps_auth.settings.auth_require_login
    deps_auth.settings.auth_require_login = True
    try:
        unauthenticated = client.get("/api/account")
        assert unauthenticated.status_code == 401

        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "change-me-admin"}
        )
        assert login.status_code == 200

        authenticated = client.get("/api/account")
        assert authenticated.status_code == 200
    finally:
        deps_auth.settings.auth_require_login = previous
        client.post("/api/auth/logout")


def test_trade_preview_logs_request_scoped_event(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="traders_cockpit")

    setup = client.get("/api/setup/AAPL").json()
    response = client.post(
        "/api/trade/preview",
        headers={REQUEST_ID_HEADER: "req-preview-1"},
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "riskPct": 1,
            "order": simple_entry_order(limitPrice=setup["entry"]),
        },
    )

    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER) == "req-preview-1"
    events = structured_events(caplog)
    preview_event = next(event for event in events if event.get("event") == "trade.preview")
    assert preview_event["request_id"] == "req-preview-1"
    assert preview_event["symbol"] == "AAPL"
    assert preview_event["order_type"] == "limit"
    assert preview_event["outcome"] == "success"


def test_websocket_subscribe_logs_lifecycle_and_propagates_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="traders_cockpit")
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
            "order": simple_entry_order(orderType="market"),
        },
    )
    assert enter.status_code == 200

    with client.websocket_connect(
        "/ws/cockpit?request_id=req-ws-connect-1&client_session_id=ws-client-1"
    ) as websocket:
        websocket.send_text(
            json.dumps(
                {
                    "action": "subscribe_price",
                    "symbol": "AAPL",
                    "requestId": "req-ws-message-1",
                    "clientSessionId": "ws-client-1",
                }
            )
        )
        payload = json.loads(websocket.receive_text())

    assert payload["type"] == "price_update"
    assert payload["symbol"] == "AAPL"
    assert payload["requestId"] == "req-ws-message-1"

    events = structured_events(caplog)
    connect_event = next(event for event in events if event.get("event") == "ws.connect")
    message_event = next(event for event in events if event.get("event") == "ws.message.received")
    broadcast_event = next(
        event
        for event in events
        if event.get("event") == "ws.broadcast"
        and event.get("event_type") == "price_update"
        and event.get("request_id") == "req-ws-message-1"
    )
    disconnect_event = next(event for event in events if event.get("event") == "ws.disconnect")

    assert connect_event["request_id"] == "req-ws-connect-1"
    assert connect_event["client_session_id"] == "ws-client-1"
    assert connect_event["channel"] == "cockpit"
    assert message_event["request_id"] == "req-ws-message-1"
    assert message_event["client_session_id"] == "ws-client-1"
    assert message_event["action"] == "subscribe_price"
    assert message_event["symbol"] == "AAPL"
    assert broadcast_event["request_id"] == "req-ws-message-1"
    assert broadcast_event["client_session_id"] == "ws-client-1"
    assert broadcast_event["event_type"] == "price_update"
    assert broadcast_event["symbol"] == "AAPL"
    assert disconnect_event["request_id"] == "req-ws-connect-1"
    assert disconnect_event["client_session_id"] == "ws-client-1"


def test_trade_lifecycle() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
        },
    )
    assert enter.status_code == 200
    position = enter.json()
    assert position["phase"] in {"trade_entered", "entry_pending"}

    if position["phase"] == "entry_pending":
        blocked_stops = client.post(
            "/api/trade/stops",
            json={
                "symbol": "AAPL",
                "stopMode": 3,
                "stopModes": [
                    {"mode": "stop", "pct": 33.0},
                    {"mode": "stop", "pct": 66.0},
                    {"mode": "stop", "pct": 100.0},
                ],
            },
        )
        assert blocked_stops.status_code == 400
        assert "until the entry order is filled" in blocked_stops.text
        return

    stops = client.post(
        "/api/trade/stops",
        json={
            "symbol": "AAPL",
            "stopMode": 3,
            "stopModes": [
                {"mode": "stop", "pct": 33.0},
                {"mode": "stop", "pct": 66.0},
                {"mode": "stop", "pct": 100.0},
            ],
        },
    )
    assert stops.status_code == 200
    assert stops.json()["phase"] == "protected"

    profit = client.post(
        "/api/trade/profit", json={"symbol": "AAPL", "trancheModes": tranche_modes()}
    )
    assert profit.status_code == 200
    profit_state = profit.json()
    assert profit_state["phase"] in {"P2_done", "runner_only", "closed"}
    assert len(profit_state["orders"]) >= 4
    assert all(
        order["id"] == profit_state["rootOrderId"]
        or order.get("parentId") == profit_state["rootOrderId"]
        for order in profit_state["orders"]
    )


def test_paper_limit_entry_stays_pending_and_can_be_canceled() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    pending_limit = round((setup["entry"] + setup["finalStop"]) / 2, 2)

    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
            "order": simple_entry_order(limitPrice=pending_limit),
        },
    )
    assert enter.status_code == 200
    position = enter.json()
    assert position["phase"] == "entry_pending"
    root_order = next(order for order in position["orders"] if order["tranche"] == "AAPL")
    assert root_order["status"] == "PENDING"
    assert root_order["cancelable"] is True
    assert root_order["brokerOrderId"]

    recent_orders = client.get("/api/orders")
    assert recent_orders.status_code == 200
    assert any(
        order["brokerOrderId"] == root_order["brokerOrderId"] for order in recent_orders.json()
    )

    cancel = client.delete(f"/api/orders/{root_order['brokerOrderId']}")
    assert cancel.status_code == 200
    canceled_order = cancel.json()
    assert canceled_order["status"] == "CANCELED"

    positions = client.get("/api/positions")
    assert positions.status_code == 200
    closed_position = next(
        position for position in positions.json() if position["symbol"] == "AAPL"
    )
    assert closed_position["phase"] == "closed"


def test_preview_trade_supports_sell_side_and_rejects_invalid_short_stop() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    short_stop = round(max(setup["hod"], setup["entry"] + 1), 2)

    preview = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": short_stop,
            "riskPct": 0.2,
            "order": simple_entry_order("sell", timeInForce="gtc", limitPrice=setup["entry"]),
        },
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["perShareRisk"] == round(short_stop - setup["entry"], 2)
    assert payload["shares"] > 0

    invalid = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": round(setup["entry"] - 1, 2),
            "riskPct": 0.2,
            "order": simple_entry_order("sell", limitPrice=setup["entry"]),
        },
    )
    assert invalid.status_code == 400
    assert "above entry for short positions" in invalid.text


def test_short_trade_uses_buy_to_cover_for_stops_and_profit_orders() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    short_stop = round(max(setup["hod"], setup["entry"] + 1), 2)

    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": short_stop,
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
            "order": simple_entry_order("sell", limitPrice=setup["entry"]),
        },
    )
    assert enter.status_code == 200
    position = enter.json()
    assert position["phase"] == "trade_entered"
    root_order = next(
        order for order in position["orders"] if order["id"] == position["rootOrderId"]
    )
    assert root_order["side"] == "SELL"

    stops = client.post(
        "/api/trade/stops",
        json={
            "symbol": "AAPL",
            "stopMode": 3,
            "stopModes": [
                {"mode": "stop", "pct": 33.0},
                {"mode": "stop", "pct": 66.0},
                {"mode": "stop", "pct": 100.0},
            ],
        },
    )
    assert stops.status_code == 200
    protected = stops.json()
    stop_orders = [order for order in protected["orders"] if order["type"] == "STOP"]
    assert len(stop_orders) == 3
    assert all(order["side"] == "BUY" for order in stop_orders)
    assert all(order["price"] > protected["setup"]["entry"] for order in stop_orders)

    profit = client.post(
        "/api/trade/profit",
        json={"symbol": "AAPL", "trancheModes": tranche_modes()},
    )
    assert profit.status_code == 200
    profit_state = profit.json()
    filled_limits = [
        order
        for order in profit_state["orders"]
        if order["type"] == "LMT" and order.get("parentId") == profit_state["rootOrderId"]
    ]
    assert filled_limits
    assert all(order["side"] == "BUY" for order in filled_limits)


def test_preview_rejects_stop_ioc_combo() -> None:
    setup = client.get("/api/setup/AAPL").json()

    response = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": round(setup["entry"] - 1, 2),
            "riskPct": 1,
            "order": simple_entry_order(
                orderType="stop",
                timeInForce="ioc",
                stopPrice=round(setup["entry"] + 1, 2),
                limitPrice=None,
            ),
        },
    )

    assert response.status_code == 400
    assert "STOP orders do not support IOC time-in-force." in response.text


def test_preview_rejects_bracket_with_invalid_tif() -> None:
    setup = client.get("/api/setup/AAPL").json()

    response = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": round(setup["entry"] - 1, 2),
            "riskPct": 1,
            "order": simple_entry_order(
                orderType="market",
                timeInForce="fok",
                orderClass="bracket",
                limitPrice=None,
                takeProfit={"limitPrice": round(setup["entry"] + 1, 2)},
                stopLoss={"stopPrice": round(setup["entry"] - 1, 2), "limitPrice": None},
            ),
        },
    )

    assert response.status_code == 400
    assert "Attached exit orders require DAY or GTC time-in-force." in response.text


def test_preview_rejects_extended_hours_non_simple_limit() -> None:
    setup = client.get("/api/setup/AAPL").json()

    response = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": round(setup["entry"] - 1, 2),
            "riskPct": 1,
            "order": simple_entry_order(
                orderType="limit",
                timeInForce="day",
                orderClass="bracket",
                extendedHours=True,
                limitPrice=setup["entry"],
                takeProfit={"limitPrice": round(setup["entry"] + 1, 2)},
                stopLoss={"stopPrice": round(setup["entry"] - 1, 2), "limitPrice": None},
            ),
        },
    )

    assert response.status_code == 400
    assert "Extended-hours is only available for simple limit entries." in response.text


def test_preview_rejects_oco_entry_order_class() -> None:
    setup = client.get("/api/setup/AAPL").json()

    response = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "manual",
            "stopPrice": round(setup["entry"] - 1, 2),
            "riskPct": 1,
            "order": simple_entry_order(
                orderType="limit",
                timeInForce="day",
                orderClass="oco",
                limitPrice=setup["entry"],
                takeProfit={"limitPrice": round(setup["entry"] + 1, 2)},
                stopLoss={"stopPrice": round(setup["entry"] - 1, 2), "limitPrice": None},
            ),
        },
    )

    assert response.status_code == 400
    assert "exit-only Alpaca order class" in response.text


def test_three_stop_mode_defaults_to_33_33_34_when_pct_is_blank() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
        },
    )
    assert enter.status_code == 200

    stops = client.post(
        "/api/trade/stops",
        json={
            "symbol": "AAPL",
            "stopMode": 3,
            "stopModes": [
                {"mode": "stop", "pct": None},
                {"mode": "stop", "pct": None},
                {"mode": "stop", "pct": None},
            ],
        },
    )
    assert stops.status_code == 200
    protected = stops.json()
    stop_orders = [order for order in protected["orders"] if order["type"] == "STOP"]
    assert len(stop_orders) == 3

    stop_range = round(setup["entry"] - setup["finalStop"], 2)
    expected_prices = [
        round(setup["entry"] - stop_range * 0.33, 2),
        round(setup["entry"] - stop_range * 0.33, 2),
        round(setup["entry"] - stop_range * 0.34, 2),
    ]
    assert [order["price"] for order in stop_orders] == expected_prices


def test_account_update() -> None:
    update = client.put(
        "/api/account/settings", json={"equity": 30000, "risk_pct": 1.5, "mode": "paper"}
    )
    assert update.status_code == 200
    data = update.json()
    assert data["equity"] == 30000
    assert data["risk_pct"] == 1.5
    assert data["effective_mode"] == "paper"
    assert data["max_open_positions"] >= 1


def test_live_mode_is_gated_by_default() -> None:
    update = client.put(
        "/api/account/settings", json={"equity": 30000, "risk_pct": 1.5, "mode": "alpaca_live"}
    )
    assert update.status_code == 400
    assert "Live trading is disabled" in update.text


def test_activity_log_can_be_cleared() -> None:
    before = client.get("/api/activity-log")
    assert before.status_code == 200
    assert len(before.json()) >= 1

    cleared = client.delete("/api/activity-log")
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] >= 1

    after = client.get("/api/activity-log")
    assert after.status_code == 200
    messages = [entry["message"] for entry in after.json()]
    assert "Log cleared." in messages


def test_runner_cannot_be_reexecuted_once_active() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
        },
    )
    assert enter.status_code == 200
    client.post(
        "/api/trade/stops",
        json={
            "symbol": "AAPL",
            "stopMode": 3,
            "stopModes": [
                {"mode": "stop", "pct": 33.0},
                {"mode": "stop", "pct": 66.0},
                {"mode": "stop", "pct": 100.0},
            ],
        },
    )
    first_profit = client.post(
        "/api/trade/profit", json={"symbol": "AAPL", "trancheModes": tranche_modes()}
    )
    assert first_profit.status_code == 200
    second_profit = client.post(
        "/api/trade/profit", json={"symbol": "AAPL", "trancheModes": tranche_modes()}
    )
    assert second_profit.status_code == 400
    assert "Active TRAIL order already exists" in second_profit.text


def test_enter_trade_recovers_stale_active_orders_for_closed_symbol() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()

    with SessionLocal() as db:
        db.add(
            PositionEntity(
                symbol="AAPL",
                phase="closed",
                entry_price=setup["entry"],
                live_price=setup["last"],
                shares=setup["shares"],
                stop_ref="lod",
                stop_price=setup["finalStop"],
                tranche_count=3,
                tranche_modes=tranche_modes(),
                stop_modes=[{"mode": "stop", "pct": None} for _ in range(3)],
                tranches=[],
                setup_snapshot=setup,
                root_order_id="ORD-0001",
            )
        )
        db.add(
            OrderEntity(
                order_id="ORD-0002",
                broker_order_id="paper-stale",
                symbol="AAPL",
                type="STOP",
                qty=10,
                orig_qty=10,
                price=setup["finalStop"],
                status="ACTIVE",
                tranche_label="S1",
                covered_tranches=["T1"],
                parent_id="ORD-0001",
            )
        )
        db.commit()

    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
        },
    )
    assert enter.status_code == 200

    with SessionLocal() as db:
        stale = db.scalar(select(OrderEntity).where(OrderEntity.order_id == "ORD-0002"))
        assert stale is not None
        assert stale.status == "CANCELED"


def test_off_hours_queue_for_open_creates_pending_entry() -> None:
    original_get_setup = service.get_setup

    def fake_setup(_db, _symbol: str):
        setup = original_get_setup(_db, "AAPL")
        return setup.model_copy(
            update={
                "sessionState": "closed",
                "quoteState": "cached_quote",
                "executionProvider": "alpaca_paper",
            }
        )

    service.get_setup = fake_setup
    try:
        setup = client.get("/api/setup/AAPL").json()
        enter = client.post(
            "/api/trade/enter",
            json={
                "symbol": "AAPL",
                "entry": setup["entry"],
                "stopRef": "lod",
                "stopPrice": setup["finalStop"],
                "trancheCount": 3,
                "trancheModes": tranche_modes(),
                "offHoursMode": "queue_for_open",
            },
        )
        assert enter.status_code == 200
        pending = enter.json()
        assert pending["phase"] == "entry_pending"

        flatten = client.post("/api/trade/flatten", json={"symbol": "AAPL"})
        assert flatten.status_code == 200
        assert flatten.json()["phase"] == "closed"
    finally:
        service.get_setup = original_get_setup


def test_stop_fill_reconciles_realized_loss_for_only_hit_tranche() -> None:
    client.put(
        "/api/account/settings",
        json={"equity": 1000000, "risk_pct": 0.2, "mode": "paper"},
    )
    setup = client.get("/api/setup/AAPL").json()
    enter = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
        },
    )
    assert enter.status_code == 200

    stops = client.post(
        "/api/trade/stops",
        json={
            "symbol": "AAPL",
            "stopMode": 3,
            "stopModes": [
                {"mode": "stop", "pct": 33.0},
                {"mode": "stop", "pct": 66.0},
                {"mode": "stop", "pct": 100.0},
            ],
        },
    )
    assert stops.status_code == 200
    protected = stops.json()
    s1 = next(
        order
        for order in protected["orders"]
        if order["type"] == "STOP" and order["tranche"] == "S1"
    )
    s2 = next(
        order
        for order in protected["orders"]
        if order["type"] == "STOP" and order["tranche"] == "S2"
    )
    assert s1["price"] > s2["price"]

    with SessionLocal() as db:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == "AAPL"))
        assert position is not None
        position.live_price = round((s1["price"] + s2["price"]) / 2, 2)
        db.commit()

    reconciled = client.get("/api/positions/AAPL")
    assert reconciled.status_code == 200
    payload = reconciled.json()
    sold = [tranche for tranche in payload["tranches"] if tranche["status"] == "sold"]
    active = [tranche for tranche in payload["tranches"] if tranche["status"] == "active"]
    assert len(sold) == 1
    assert len(active) == 2
    assert sold[0]["exitOrderType"] == "STOP"
    assert sold[0]["exitPrice"] == s1["price"]
    assert sold[0]["exitFilledAt"] is not None
    filled_stop_orders = [
        order
        for order in payload["orders"]
        if order["type"] == "STOP" and order["status"] == "FILLED"
    ]
    assert len(filled_stop_orders) == 1
    assert filled_stop_orders[0]["tranche"] == "S1"


def test_setup_uses_cached_quote_metadata_when_alpaca_quote_is_off_hours() -> None:
    original_market_data = service.market_data.get_setup_data

    def fake_market_data(symbol: str):
        fallback = original_market_data("AAPL")
        return SetupMarketData(
            symbol=symbol.upper(),
            provider="alpaca_quote",
            provider_state="real_quote_fallback_technicals",
            quote_provider="alpaca",
            technicals_provider="mock",
            quote_is_real=True,
            technicals_are_fallback=True,
            fallback_reason="technicals_fallback_only",
            quote_timestamp=fallback.quote_timestamp,
            session_state="closed",
            quote_state="cached_quote",
            entry_basis=fallback.entry_basis,
            bid=fallback.bid,
            ask=fallback.ask,
            last=fallback.last,
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

    service.market_data.get_setup_data = fake_market_data
    try:
        response = client.get("/api/setup/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["quoteProvider"] == "alpaca"
        assert data["sessionState"] == "closed"
        assert data["quoteState"] == "cached_quote"
    finally:
        service.market_data.get_setup_data = original_market_data


def test_recent_orders_merge_broker_state_and_cancel() -> None:
    with SessionLocal() as db:
        db.add(
            OrderEntity(
                order_id="ORD-9001",
                broker_order_id="broker-1",
                symbol="AAPL",
                type="LMT",
                qty=10,
                orig_qty=10,
                price=101.25,
                status="PENDING",
                tranche_label="AAPL",
                covered_tranches=[],
                parent_id=None,
            )
        )
        db.commit()

    canceled: list[str] = []
    original_list_recent_orders = service.broker.list_recent_orders
    original_get_order = service.broker.get_order
    original_cancel_order = service.broker.cancel_order

    def fake_list_recent_orders(limit: int = 50):
        return [
            {
                "id": "broker-1",
                "client_order_id": "client-1",
                "symbol": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": "10",
                "filled_qty": "0",
                "limit_price": "101.25",
                "status": "accepted",
                "created_at": "2026-03-22T10:00:00Z",
                "updated_at": "2026-03-22T10:00:05Z",
            },
            {
                "id": "broker-2",
                "client_order_id": "client-2",
                "symbol": "MSFT",
                "side": "sell",
                "type": "market",
                "qty": "5",
                "filled_qty": "5",
                "filled_avg_price": "380.10",
                "status": "filled",
                "created_at": "2026-03-22T09:59:00Z",
                "updated_at": "2026-03-22T09:59:10Z",
                "filled_at": "2026-03-22T09:59:10Z",
            },
        ][:limit]

    def fake_get_order(broker_order_id: str):
        if broker_order_id == "broker-1" and "broker-1" not in canceled:
            return {
                "id": "broker-1",
                "client_order_id": "client-1",
                "symbol": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": "10",
                "filled_qty": "0",
                "limit_price": "101.25",
                "status": "accepted",
                "created_at": "2026-03-22T10:00:00Z",
                "updated_at": "2026-03-22T10:00:05Z",
            }
        if broker_order_id == "broker-1":
            return {
                "id": "broker-1",
                "client_order_id": "client-1",
                "symbol": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": "10",
                "filled_qty": "0",
                "limit_price": "101.25",
                "status": "canceled",
                "created_at": "2026-03-22T10:00:00Z",
                "updated_at": "2026-03-22T10:01:00Z",
            }
        return None

    def fake_cancel_order(broker_order_id: str):
        canceled.append(broker_order_id)

    service.broker.list_recent_orders = fake_list_recent_orders
    service.broker.get_order = fake_get_order
    service.broker.cancel_order = fake_cancel_order
    try:
        response = client.get("/api/orders")
        assert response.status_code == 200
        orders = response.json()
        assert orders[0]["brokerOrderId"] == "broker-1"
        assert orders[0]["cancelable"] is True
        assert orders[0]["symbol"] == "AAPL"
        assert any(order["brokerOrderId"] == "broker-2" for order in orders)

        cancel_response = client.delete("/api/orders/broker-1")
        assert cancel_response.status_code == 200
        canceled_view = cancel_response.json()
        assert canceled_view["status"] == "CANCELED"
        assert canceled == ["broker-1"]

        with SessionLocal() as db:
            local = db.scalar(select(OrderEntity).where(OrderEntity.order_id == "ORD-9001"))
            assert local is not None
            assert local.status == "CANCELED"
    finally:
        service.broker.list_recent_orders = original_list_recent_orders
        service.broker.get_order = original_get_order
        service.broker.cancel_order = original_cancel_order


def test_cancel_recent_order_logs_request_scoped_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with SessionLocal() as db:
        db.add(
            OrderEntity(
                order_id="ORD-9201",
                broker_order_id="broker-log-1",
                symbol="AAPL",
                type="LMT",
                qty=10,
                orig_qty=10,
                price=101.25,
                status="PENDING",
                tranche_label="AAPL",
                covered_tranches=[],
                parent_id=None,
            )
        )
        db.commit()

    caplog.set_level(logging.INFO, logger="traders_cockpit")
    original_get_order = service.broker.get_order
    original_cancel_order = service.broker.cancel_order

    def fake_get_order(broker_order_id: str):
        if broker_order_id != "broker-log-1":
            return None
        return {
            "id": "broker-log-1",
            "client_order_id": "client-log-1",
            "symbol": "AAPL",
            "side": "buy",
            "type": "limit",
            "qty": "10",
            "filled_qty": "0",
            "limit_price": "101.25",
            "status": "accepted",
            "created_at": "2026-03-22T10:00:00Z",
            "updated_at": "2026-03-22T10:00:05Z",
        }

    def fake_cancel_order(_broker_order_id: str):
        return None

    service.broker.get_order = fake_get_order
    service.broker.cancel_order = fake_cancel_order
    try:
        response = client.delete(
            "/api/orders/broker-log-1",
            headers={REQUEST_ID_HEADER: "req-cancel-1"},
        )
        assert response.status_code == 200
        assert response.headers.get(REQUEST_ID_HEADER) == "req-cancel-1"
        events = structured_events(caplog)
        cancel_event = next(event for event in events if event.get("event") == "orders.cancel")
        assert cancel_event["request_id"] == "req-cancel-1"
        assert cancel_event["broker_order_id"] == "broker-log-1"
        assert cancel_event["symbol"] == "AAPL"
        assert cancel_event["outcome"] == "success"
    finally:
        service.broker.get_order = original_get_order
        service.broker.cancel_order = original_cancel_order


def test_cancel_recent_root_order_closes_pending_position() -> None:
    with SessionLocal() as db:
        db.add(
            PositionEntity(
                symbol="AMD",
                phase="entry_pending",
                entry_price=201.22,
                live_price=201.22,
                shares=10,
                stop_ref="lod",
                stop_price=198.33,
                tranche_count=3,
                tranche_modes=tranche_modes(),
                stop_modes=[{"mode": "stop", "pct": None} for _ in range(3)],
                tranches=[
                    {
                        "id": "T1",
                        "qty": 3,
                        "stop": 198.33,
                        "label": "T1",
                        "status": "active",
                        "mode": "limit",
                        "trail": 2.0,
                        "trailUnit": "$",
                        "runnerStop": None,
                    },
                    {
                        "id": "T2",
                        "qty": 3,
                        "stop": 198.33,
                        "label": "T2",
                        "status": "active",
                        "mode": "limit",
                        "trail": 2.0,
                        "trailUnit": "$",
                        "runnerStop": None,
                    },
                    {
                        "id": "T3",
                        "qty": 4,
                        "stop": 198.33,
                        "label": "T3",
                        "status": "active",
                        "mode": "limit",
                        "trail": 2.0,
                        "trailUnit": "$",
                        "runnerStop": None,
                    },
                ],
                setup_snapshot=service.get_setup(db, "AAPL").model_dump(mode="json"),
                root_order_id="ORD-9010",
            )
        )
        db.add(
            OrderEntity(
                order_id="ORD-9010",
                broker_order_id="broker-root",
                symbol="AMD",
                type="MKT",
                qty=10,
                orig_qty=10,
                price=201.22,
                status="PENDING",
                tranche_label="AMD",
                covered_tranches=[],
                parent_id=None,
            )
        )
        db.commit()

    original_get_order = service.broker.get_order
    original_cancel_order = service.broker.cancel_order

    def fake_get_order(broker_order_id: str):
        if broker_order_id == "broker-root":
            return {
                "id": "broker-root",
                "client_order_id": "client-root",
                "symbol": "AMD",
                "side": "buy",
                "type": "market",
                "qty": "10",
                "filled_qty": "0",
                "status": "accepted",
                "created_at": "2026-03-22T10:00:00Z",
                "updated_at": "2026-03-22T10:00:05Z",
            }
        return None

    canceled: list[str] = []

    def fake_cancel_order(broker_order_id: str):
        canceled.append(broker_order_id)

    service.broker.get_order = fake_get_order
    service.broker.cancel_order = fake_cancel_order
    try:
        response = client.delete("/api/orders/broker-root")
        assert response.status_code == 200
        assert canceled == ["broker-root"]
        with SessionLocal() as db:
            position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == "AMD"))
            assert position is not None
            assert position.phase == "closed"
            assert all(tranche["status"] == "canceled" for tranche in position.tranches)
    finally:
        service.broker.get_order = original_get_order
        service.broker.cancel_order = original_cancel_order
