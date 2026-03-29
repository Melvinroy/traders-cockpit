from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    sys.path.insert(0, str(backend_dir))

    from app.db.session import SessionLocal
    from app.main import service

    with SessionLocal() as db:
        positions = service.get_positions(db)
        account = service.get_account(db)
        local_orders = service.get_recent_orders(db, limit=200)
        try:
            broker_orders = service.broker.list_recent_orders(limit=200)
        except ValueError:
            broker_orders = []

    broker_by_id = {
        str(order.get("id") or ""): order
        for order in broker_orders
        if isinstance(order, dict) and order.get("id")
    }
    issues: list[str] = []

    if account.reconcileStatus != "synchronized":
        issues.append(f"Account reconciliation is {account.reconcileStatus}.")

    unsynchronized_positions = [
        f"{position.symbol}:{position.reconcileStatus}"
        for position in positions
        if position.reconcileStatus != "synchronized"
    ]
    if unsynchronized_positions:
        issues.append(
            "Unsynchronized positions detected: " + ", ".join(unsynchronized_positions)
        )

    for order in local_orders:
        if not order.brokerOrderId:
            continue
        broker_order = broker_by_id.get(order.brokerOrderId)
        if broker_order is None:
            continue
        broker_status = str(broker_order.get("status") or "").upper()
        if broker_status and broker_status != order.status:
            issues.append(
                f"Order {order.id} status drift: local={order.status} broker={broker_status}"
            )

    summary = {
        "pass": not issues,
        "brokerMode": service.settings.normalized_broker_mode,
        "accountReconcileStatus": account.reconcileStatus,
        "positionCount": len(positions),
        "orderCount": len(local_orders),
        "brokerOrderCount": len(broker_by_id),
        "issues": issues,
    }
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["pass"] else 1)


if __name__ == "__main__":
    main()
