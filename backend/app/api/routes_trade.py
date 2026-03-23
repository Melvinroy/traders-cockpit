from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import require_session
from app.db.session import get_db
from app.schemas.cockpit import (
    MoveToBeRequest,
    PositionView,
    ProfitRequest,
    StopsRequest,
    TradeEnterRequest,
    TradePreviewRequest,
)
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api/trade", tags=["trade"], dependencies=[Depends(require_session)])

    @router.post("/preview")
    def preview(payload: TradePreviewRequest, db: Session = Depends(get_db)) -> dict:
        try:
            return service.preview_trade(db, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/enter", response_model=PositionView)
    async def enter(payload: TradeEnterRequest, db: Session = Depends(get_db)) -> PositionView:
        try:
            return await service.enter_trade(db, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/stops", response_model=PositionView)
    async def stops(payload: StopsRequest, db: Session = Depends(get_db)) -> PositionView:
        try:
            return await service.apply_stops(db, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profit", response_model=PositionView)
    async def profit(payload: ProfitRequest, db: Session = Depends(get_db)) -> PositionView:
        try:
            return await service.execute_profit_plan(db, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/flatten", response_model=PositionView)
    async def flatten(payload: MoveToBeRequest, db: Session = Depends(get_db)) -> PositionView:
        try:
            return await service.flatten(db, payload.symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/move_to_be", response_model=PositionView)
    async def move_to_be(payload: MoveToBeRequest, db: Session = Depends(get_db)) -> PositionView:
        try:
            return await service.move_to_be(db, payload.symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
