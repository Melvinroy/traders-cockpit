from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import require_webhook_secret
from app.db.session import get_db
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api/broker", tags=["broker"])

    @router.post("/webhook")
    async def broker_webhook(
        payload: dict[str, Any] = Body(default_factory=dict),
        db: Session = Depends(get_db),
        _: None = Depends(require_webhook_secret),
    ) -> dict[str, Any]:
        try:
            result = service.ingest_broker_webhook(db, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        db.commit()

        for symbol in result.get("symbols", []):
            try:
                view = service.get_position(db, symbol)
            except ValueError:
                continue
            await service.broadcast_position_projection(db, view)

        if result.get("accountChanged"):
            await service.broadcast_account_update(db)

        return {
            "received": result.get("received", 0),
            "processedOrders": result.get("processedOrders", 0),
            "processedFills": result.get("processedFills", 0),
            "processedAccounts": result.get("processedAccounts", 0),
            "symbols": result.get("symbols", []),
            "accountChanged": bool(result.get("accountChanged")),
        }

    return router
