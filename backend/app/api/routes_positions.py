from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import require_session, require_write_guard
from app.db.session import get_db
from app.schemas.cockpit import OrderView, PositionView
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["positions"], dependencies=[Depends(require_session)])

    @router.get("/positions", response_model=list[PositionView])
    def get_positions(db: Session = Depends(get_db)) -> list[PositionView]:
        return service.get_positions(db)

    @router.get("/positions/{symbol}", response_model=PositionView)
    def get_position(symbol: str, db: Session = Depends(get_db)) -> PositionView:
        return service.get_position(db, symbol)

    @router.get("/orders/{symbol}", response_model=list[OrderView])
    def get_orders(symbol: str, db: Session = Depends(get_db)) -> list[OrderView]:
        return service.get_orders(db, symbol)

    @router.get("/orders", response_model=list[OrderView])
    def get_recent_orders(db: Session = Depends(get_db)) -> list[OrderView]:
        return service.get_recent_orders(db)

    @router.delete("/orders/{broker_order_id}", response_model=OrderView)
    def cancel_order(
        broker_order_id: str,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> OrderView:
        try:
            return service.cancel_recent_order(db, broker_order_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
