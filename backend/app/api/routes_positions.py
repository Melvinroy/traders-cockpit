from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cockpit import OrderView, PositionView
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["positions"])

    @router.get("/positions", response_model=list[PositionView])
    def get_positions(db: Session = Depends(get_db)) -> list[PositionView]:
        return service.get_positions(db)

    @router.get("/positions/{symbol}", response_model=PositionView)
    def get_position(symbol: str, db: Session = Depends(get_db)) -> PositionView:
        return service.get_position(db, symbol)

    @router.get("/orders/{symbol}", response_model=list[OrderView])
    def get_orders(symbol: str, db: Session = Depends(get_db)) -> list[OrderView]:
        return service.get_orders(db, symbol)

    return router
