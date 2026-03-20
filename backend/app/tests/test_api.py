from __future__ import annotations

import os
from pathlib import Path

import pytest

db_path = Path(__file__).resolve().parent / "test.db"
if db_path.exists():
    db_path.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["AUTH_REQUIRE_LOGIN"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.entities import OrderEntity, PositionEntity, TradeLogEntity  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    with SessionLocal() as db:
        db.query(OrderEntity).delete()
        db.query(PositionEntity).delete()
        db.query(TradeLogEntity).delete()
        db.commit()
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
    assert data["entry"] > data["finalStop"]
    assert data["shares"] > 0


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


def test_account_update() -> None:
    update = client.put("/api/account/settings", json={"equity": 30000, "risk_pct": 1.5, "mode": "paper"})
    assert update.status_code == 200
    data = update.json()
    assert data["equity"] == 30000
    assert data["risk_pct"] == 1.5


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
    assert "Activity log cleared." in messages
