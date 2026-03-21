from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import select
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

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.entities import OrderEntity, PositionEntity, TradeLogEntity  # noqa: E402
from app.services.auth import get_auth_store  # noqa: E402
from app.core.config import Settings  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)
auth_store = get_auth_store(Settings.from_env())
auth_store.bootstrap_users(
    admin_username="admin",
    admin_password="admin123!",
    trader_username="trader",
    trader_password="trader123!",
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
        admin_password="admin123!",
        trader_username="trader",
        trader_password="trader123!",
        seed_enabled=True,
    )
    yield


def tranche_modes() -> list[dict]:
    return [
        {"mode": "limit", "trail": 2, "trailUnit": "$", "target": "1R", "manualPrice": None},
        {"mode": "limit", "trail": 2, "trailUnit": "$", "target": "2R", "manualPrice": None},
        {"mode": "runner", "trail": 2, "trailUnit": "$", "target": "3R", "manualPrice": None},
    ]


def test_setup_endpoint_returns_contract() -> None:
    response = client.get("/api/setup/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["provider"] in {"mock", "alpaca_quote"}
    assert data["entryBasis"] == "bid_ask_midpoint"
    assert data["entry"] > data["finalStop"]
    assert data["shares"] > 0


def test_login_creates_session_and_me_resolves_user() -> None:
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123!"})
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
    assert position["phase"] == "trade_entered"

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

    profit = client.post("/api/trade/profit", json={"symbol": "AAPL", "trancheModes": tranche_modes()})
    assert profit.status_code == 200
    profit_state = profit.json()
    assert profit_state["phase"] in {"P2_done", "runner_only", "closed"}
    assert len(profit_state["orders"]) >= 4
    assert all(
        order["id"] == profit_state["rootOrderId"] or order.get("parentId") == profit_state["rootOrderId"]
        for order in profit_state["orders"]
    )


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
    update = client.put("/api/account/settings", json={"equity": 30000, "risk_pct": 1.5, "mode": "paper"})
    assert update.status_code == 200
    data = update.json()
    assert data["equity"] == 30000
    assert data["risk_pct"] == 1.5
    assert data["effective_mode"] == "paper"
    assert data["max_open_positions"] >= 1


def test_live_mode_is_gated_by_default() -> None:
    update = client.put("/api/account/settings", json={"equity": 30000, "risk_pct": 1.5, "mode": "alpaca_live"})
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
    first_profit = client.post("/api/trade/profit", json={"symbol": "AAPL", "trancheModes": tranche_modes()})
    assert first_profit.status_code == 200
    second_profit = client.post("/api/trade/profit", json={"symbol": "AAPL", "trancheModes": tranche_modes()})
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
