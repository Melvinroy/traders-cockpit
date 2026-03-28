from __future__ import annotations

# ruff: noqa: E402

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

db_path = Path(__file__).resolve().parent / "test.db"
if db_path.exists():
    db_path.unlink()
auth_db_path = Path(__file__).resolve().parent / "auth-test.db"
if auth_db_path.exists():
    auth_db_path.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["AUTH_DB_PATH"] = str(auth_db_path)
os.environ["AUTH_REQUIRE_LOGIN"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.adapters.broker import AlpacaBrokerAdapter  # noqa: E402
from app.adapters.market_data import SetupMarketData  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app, service  # noqa: E402
from app.models.entities import (
    AccountSettingsEntity,
    AccountSnapshotEntity,
    BrokerFillEntity,
    BrokerOrderEntity,
    EventLogEntity,
    OrderEntity,
    OrderIntentEntity,
    PositionEntity,
    PositionProjectionEntity,
    ReconcileRunEntity,
    TradeLogEntity,
)  # noqa: E402
from app.schemas.cockpit import TrancheMode  # noqa: E402
from app.api import deps_auth  # noqa: E402
from app.core.config import Settings, _normalize_database_url  # noqa: E402
from app.services.auth import get_auth_store  # noqa: E402

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
        db.query(ReconcileRunEntity).delete()
        db.query(AccountSnapshotEntity).delete()
        db.query(PositionProjectionEntity).delete()
        db.query(BrokerFillEntity).delete()
        db.query(BrokerOrderEntity).delete()
        db.query(OrderIntentEntity).delete()
        db.query(EventLogEntity).delete()
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
    assert data["reconcileStatus"] in {"synchronized", "pending", "stale"}
    assert "lastReconciledAt" in data
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


def test_broker_mode_aliases_normalize_to_legacy_runtime_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BROKER_MODE", "sim_paper")
    assert Settings.from_env().broker_mode == "paper"
    assert Settings.from_env().normalized_broker_mode == "sim_paper"

    monkeypatch.setenv("BROKER_MODE", "broker_paper")
    assert Settings.from_env().broker_mode == "alpaca_paper"
    assert Settings.from_env().normalized_broker_mode == "broker_paper"

    monkeypatch.setenv("BROKER_MODE", "live")
    assert Settings.from_env().broker_mode == "alpaca_live"
    assert Settings.from_env().normalized_broker_mode == "live"


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


def test_refresh_live_mark_freezes_stale_quote_without_mutation() -> None:
    original_get_setup_data = service.market_data.get_setup_data
    with SessionLocal() as db:
        setup = service.get_setup(db, "AAPL")
        position = PositionEntity(
            symbol="AAPL",
            phase="trade_entered",
            entry_price=setup.entry,
            live_price=setup.last,
            shares=10,
            stop_ref="lod",
            stop_price=setup.finalStop,
            tranche_count=3,
            tranche_modes=tranche_modes(),
            stop_modes=[{"mode": "stop", "pct": None} for _ in range(3)],
            tranches=[],
            setup_snapshot={
                **setup.model_dump(mode="json"),
                "entryOrder": {"side": "buy"},
            },
            root_order_id="ORD-FROZEN-1",
        )
        db.add(position)
        db.commit()
        db.refresh(position)
        original_live_price = position.live_price

        def stale_market(_symbol: str):
            return SetupMarketData(
                symbol="AAPL",
                provider="alpaca_market",
                provider_state="cached_quote",
                quote_provider="alpaca",
                technicals_provider="alpaca",
                quote_is_real=True,
                technicals_are_fallback=False,
                fallback_reason=None,
                quote_timestamp=None,
                session_state="after_hours",
                quote_state="cached_quote",
                entry_basis="bid_ask_midpoint",
                bid=setup.bid,
                ask=setup.ask,
                last=setup.last + 5,
                lod=setup.lod,
                hod=setup.hod,
                prev_close=setup.prev_close,
                atr14=setup.atr14,
                sma10=setup.sma10,
                sma50=setup.sma50,
                sma200=setup.sma200,
                sma200_prev=setup.sma200_prev,
                rvol=setup.rvol,
                days_to_cover=setup.days_to_cover,
            )

        service.market_data.get_setup_data = stale_market
        try:
            service._refresh_live_mark(position)
        finally:
            service.market_data.get_setup_data = original_get_setup_data

        assert position.live_price == original_live_price
        assert position.setup_snapshot["markState"] == "frozen"
        assert "frozen" in str(position.setup_snapshot["markLabel"]).lower()


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


def test_broker_webhook_reconciles_pending_exit_order() -> None:
    with SessionLocal() as db:
        position = PositionEntity(
            symbol="AAPL",
            phase="protected",
            entry_price=100.0,
            live_price=104.0,
            shares=10,
            stop_ref="lod",
            stop_price=98.0,
            tranche_count=1,
            tranche_modes=tranche_modes()[:1],
            stop_modes=[{"mode": "stop", "pct": 100.0}],
            tranches=[
                {
                    "id": "T1",
                    "qty": 10,
                    "stop": 98.0,
                    "status": "pending_exit",
                    "filledQty": 0,
                    "remainingQty": 10,
                    "mode": "limit",
                    "trail": 2,
                    "trailUnit": "$",
                    "label": "Tranche 1",
                }
            ],
            setup_snapshot={
                "symbol": "AAPL",
                "entry": 100.0,
                "finalStop": 98.0,
                "last": 104.0,
            },
            root_order_id="ORD-ROOT-1",
            last_intent_id="intent-root-1",
            projection_version=1,
            reconcile_status="pending",
        )
        db.add(position)
        db.add(
            OrderEntity(
                order_id="ORD-ROOT-1",
                broker_order_id="broker-root-1",
                symbol="AAPL",
                type="LMT",
                qty=10,
                orig_qty=10,
                price=100.0,
                status="FILLED",
                tranche_label="ROOT",
                covered_tranches=[],
                created_at=service._broker_timestamp(
                    {"created_at": "2026-03-28T09:20:00Z"}, "created_at"
                ),
                filled_at=service._broker_timestamp(
                    {"filled_at": "2026-03-28T09:20:01Z"}, "filled_at"
                ),
                fill_price=100.0,
                filled_qty=10,
            )
        )
        db.add(
            OrderEntity(
                order_id="ORD-EXIT-1",
                broker_order_id="broker-exit-1",
                symbol="AAPL",
                type="LMT",
                qty=10,
                orig_qty=10,
                price=105.0,
                status="ACTIVE",
                intent_id="intent-exit-1",
                tranche_label="T1",
                covered_tranches=["T1"],
                parent_id="ORD-ROOT-1",
                created_at=service._broker_timestamp(
                    {"created_at": "2026-03-28T09:25:00Z"}, "created_at"
                ),
                filled_qty=0,
            )
        )
        db.commit()

    webhook = client.post(
        "/api/broker/webhook",
        json={
            "type": "trade_update",
            "order": {
                "id": "broker-exit-1",
                "symbol": "AAPL",
                "status": "filled",
                "qty": "10",
                "filled_qty": "10",
                "filled_avg_price": "105.00",
                "filled_at": "2026-03-28T09:30:00Z",
                "side": "sell",
                "type": "limit",
            },
        },
    )
    assert webhook.status_code == 200
    body = webhook.json()
    assert body["processedOrders"] == 1
    assert body["symbols"] == ["AAPL"]

    replay = client.post(
        "/api/broker/webhook",
        json={
            "type": "trade_update",
            "order": {
                "id": "broker-exit-1",
                "symbol": "AAPL",
                "status": "filled",
                "qty": "10",
                "filled_qty": "10",
                "filled_avg_price": "105.00",
                "filled_at": "2026-03-28T09:30:00Z",
                "side": "sell",
                "type": "limit",
            },
        },
    )
    assert replay.status_code == 200
    assert replay.json()["processedOrders"] == 0

    position = client.get("/api/positions/AAPL")
    assert position.status_code == 200
    position_body = position.json()
    assert position_body["phase"] == "closed"
    assert position_body["reconcileStatus"] == "synchronized"
    assert position_body["tranches"][0]["status"] == "sold"
    with SessionLocal() as db:
        fills = db.scalars(select(BrokerFillEntity)).all()
    assert len(fills) == 1


def test_get_position_prefers_projection_payload() -> None:
    with SessionLocal() as db:
        position = PositionEntity(
            symbol="MSFT",
            phase="protected",
            entry_price=100.0,
            live_price=102.0,
            shares=5,
            stop_ref="lod",
            stop_price=98.0,
            tranche_count=1,
            tranche_modes=tranche_modes()[:1],
            stop_modes=[{"mode": "stop", "pct": 100.0}],
            tranches=[
                {
                    "id": "T1",
                    "qty": 5,
                    "stop": 98.0,
                    "status": "active",
                    "filledQty": 0,
                    "remainingQty": 5,
                    "mode": "limit",
                    "trail": 2,
                    "trailUnit": "$",
                    "label": "Tranche 1",
                }
            ],
            setup_snapshot={
                "symbol": "MSFT",
                "entry": 100.0,
                "finalStop": 98.0,
                "last": 102.0,
                "entryOrder": {"side": "buy"},
            },
            root_order_id="ORD-MSFT-1",
            last_intent_id="intent-msft-1",
            projection_version=3,
            reconcile_status="synchronized",
        )
        db.add(position)
        db.flush()
        service._sync_projection(db, position)
        db.flush()
        position.phase = "closing"
        position.reconcile_status = "pending"
        db.flush()
        projected = service.get_position(db, "MSFT")

    assert projected.phase == "protected"
    assert projected.reconcileStatus == "synchronized"


def test_preview_trade_uses_live_midpoint_for_sell_side() -> None:
    setup = client.get("/api/setup/AAPL").json()
    preview = client.post(
        "/api/trade/preview",
        json={
            "symbol": "AAPL",
            "entry": 0,
            "stopRef": "lod",
            "stopPrice": setup["hodStop"],
            "riskPct": setup["riskPct"],
            "order": {"side": "sell"},
        },
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["entry"] == setup["entry"]
    assert payload["finalStop"] == setup["hodStop"]
    assert payload["shares"] >= 0


def test_enter_trade_preserves_sell_side() -> None:
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
            "stopPrice": setup["hodStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
            "order": {"side": "sell"},
        },
    )
    assert enter.status_code == 200
    position = enter.json()
    assert position["side"] == "sell"
    assert position["setup"]["entryOrder"]["side"] == "sell"


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
        "/api/account/settings",
        json={"equity": 30000, "risk_pct": 1.5, "mode": "paper"},
    )
    assert update.status_code == 200
    data = update.json()
    assert data["equity"] == 30000
    assert data["risk_pct"] == 1.5
    assert data["effective_mode"] == "paper"
    assert data["max_open_positions"] >= 1


def test_live_mode_is_gated_by_default() -> None:
    update = client.put(
        "/api/account/settings",
        json={"equity": 30000, "risk_pct": 1.5, "mode": "alpaca_live"},
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
    assert "Another trade intent is already pending for this symbol." in second_profit.text


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


def test_projection_rebuild_restores_served_position_state() -> None:
    with SessionLocal() as db:
        setup = service.get_setup(db, "AAPL")
        position = PositionEntity(
            symbol="AAPL",
            phase="trade_entered",
            entry_price=setup.entry,
            live_price=setup.last,
            shares=24,
            stop_ref="lod",
            stop_price=setup.finalStop,
            tranche_count=3,
            tranche_modes=tranche_modes(),
            stop_modes=[{"mode": "stop", "pct": None} for _ in range(3)],
            tranches=[
                {
                    "id": "T1",
                    "qty": 8,
                    "stop": setup.finalStop,
                    "label": "T1",
                    "status": "active",
                    "mode": "limit",
                    "trail": 2.0,
                    "trailUnit": "$",
                    "runnerStop": None,
                },
                {
                    "id": "T2",
                    "qty": 8,
                    "stop": setup.finalStop,
                    "label": "T2",
                    "status": "active",
                    "mode": "limit",
                    "trail": 2.0,
                    "trailUnit": "$",
                    "runnerStop": None,
                },
                {
                    "id": "T3",
                    "qty": 8,
                    "stop": setup.finalStop,
                    "label": "T3",
                    "status": "active",
                    "mode": "runner",
                    "trail": 2.0,
                    "trailUnit": "$",
                    "runnerStop": None,
                },
            ],
            setup_snapshot={
                **setup.model_dump(mode="json"),
                "entryOrder": {"side": "buy"},
            },
            root_order_id="ORD-REBUILD-1",
            projection_version=4,
            reconcile_status="synchronized",
            last_reconciled_at=datetime.now(UTC),
        )
        db.add(position)
        service._sync_projection(db, position)
        db.commit()

        expected = service.get_position(db, "AAPL").model_dump(mode="json")
        projection = db.scalar(
            select(PositionProjectionEntity).where(PositionProjectionEntity.symbol == "AAPL")
        )
        assert projection is not None
        db.delete(projection)
        db.commit()

        rebuilt = service.rebuild_position_projections(db, symbols=["AAPL"])
        db.commit()

        assert rebuilt == ["AAPL"]
        actual = service.get_position(db, "AAPL").model_dump(mode="json")

    assert actual == expected


def test_stale_reconciliation_blocks_entry_in_broker_paper_mode() -> None:
    original_mode = service.settings.broker_mode
    original_key = service.settings.alpaca_api_key_id
    original_secret = service.settings.alpaca_api_secret_key
    original_max_age = service.settings.max_reconcile_age_seconds
    original_market_data = service.market_data.get_setup_data
    try:
        service.settings.broker_mode = "alpaca_paper"
        service.settings.alpaca_api_key_id = "paper-key"
        service.settings.alpaca_api_secret_key = "paper-secret"
        service.settings.max_reconcile_age_seconds = 5
        service.market_data.get_setup_data = lambda _symbol: SetupMarketData(
            symbol="AAPL",
            provider="alpaca_market",
            provider_state="live_quote",
            quote_provider="alpaca",
            technicals_provider="alpaca",
            quote_is_real=True,
            technicals_are_fallback=False,
            fallback_reason=None,
            quote_timestamp=datetime.now(UTC),
            session_state="regular_open",
            quote_state="live_quote",
            entry_basis="bid_ask_midpoint",
            bid=101.0,
            ask=101.2,
            last=101.1,
            lod=99.5,
            hod=102.8,
            prev_close=100.0,
            atr14=1.6,
            sma10=100.5,
            sma50=98.2,
            sma200=92.4,
            sma200_prev=92.1,
            rvol=1.4,
            days_to_cover=2.0,
        )

        with SessionLocal() as db:
            db.add(
                ReconcileRunEntity(
                    run_id="rec-stale-1",
                    trigger="poll",
                    broker="alpaca_paper",
                    status="COMPLETED",
                    processed_orders=0,
                    processed_fills=0,
                    created_at=datetime.now(UTC) - timedelta(minutes=2),
                    completed_at=datetime.now(UTC) - timedelta(minutes=2),
                )
            )
            db.commit()

        setup = client.get("/api/setup/AAPL")
        assert setup.status_code == 200
        assert setup.json()["reconcileStatus"] == "stale"
        assert "Reconciliation is stale" in " ".join(setup.json()["executionBlockingReasons"])

        enter = client.post(
            "/api/trade/enter",
            json={
                "symbol": "AAPL",
                "entry": 101.1,
                "stopRef": "lod",
                "stopPrice": 99.5,
                "trancheCount": 3,
                "trancheModes": tranche_modes(),
                "order": {"side": "buy"},
            },
        )
        assert enter.status_code == 400
        assert "Reconciliation is stale and execution is blocked." in enter.text
    finally:
        service.settings.broker_mode = original_mode
        service.settings.alpaca_api_key_id = original_key
        service.settings.alpaca_api_secret_key = original_secret
        service.settings.max_reconcile_age_seconds = original_max_age
        service.market_data.get_setup_data = original_market_data


def test_duplicate_active_intent_blocks_trade_entry() -> None:
    setup = client.get("/api/setup/AAPL").json()
    with SessionLocal() as db:
        db.add(
            OrderIntentEntity(
                intent_id="intent-pending-1",
                symbol="AAPL",
                action="enter",
                side="buy",
                qty=10,
                price=101.1,
                status="broker_accepted",
                blocking_reasons=[],
                broker_order_id="broker-pending-1",
                payload={},
            )
        )
        db.commit()

    response = client.post(
        "/api/trade/enter",
        json={
            "symbol": "AAPL",
            "entry": setup["entry"],
            "stopRef": "lod",
            "stopPrice": setup["finalStop"],
            "trancheCount": 3,
            "trancheModes": tranche_modes(),
            "order": {"side": "buy"},
        },
    )

    assert response.status_code == 400
    assert "Another trade intent is already pending for this symbol." in response.text
