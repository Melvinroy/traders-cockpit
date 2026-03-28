from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps_auth import require_session, require_write_guard
from app.db.session import get_db
from app.schemas.cockpit import (
    MoveToBeRequest,
    PositionView,
    ProfitRequest,
    StopsRequest,
    TradeEnterRequest,
    TradePreviewRequest,
    TradePreviewResponse,
)
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api/trade", tags=["trade"], dependencies=[Depends(require_session)])

    @router.post("/preview", response_model=TradePreviewResponse)
    def preview(
        payload: TradePreviewRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> TradePreviewResponse:
        try:
            response = service.preview_trade(db, payload)
            log_event(
                "trade.preview",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    side=payload.order.side,
                    order_type=payload.order.orderType,
                    time_in_force=payload.order.timeInForce,
                    order_class=payload.order.orderClass,
                    outcome="success",
                ),
            )
            return response
        except ValueError as exc:
            log_event(
                "trade.preview",
                level="warning",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    side=payload.order.side,
                    order_type=payload.order.orderType,
                    time_in_force=payload.order.timeInForce,
                    order_class=payload.order.orderClass,
                    outcome="error",
                    detail=str(exc),
                ),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/enter", response_model=PositionView)
    async def enter(
        payload: TradeEnterRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> PositionView:
        try:
            response = await service.enter_trade(db, payload)
            log_event(
                "trade.enter",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    side=payload.order.side,
                    order_type=payload.order.orderType,
                    time_in_force=payload.order.timeInForce,
                    order_class=payload.order.orderClass,
                    phase=response.phase,
                    outcome="success",
                ),
            )
            return response
        except ValueError as exc:
            log_event(
                "trade.enter",
                level="warning",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    side=payload.order.side,
                    order_type=payload.order.orderType,
                    time_in_force=payload.order.timeInForce,
                    order_class=payload.order.orderClass,
                    outcome="error",
                    detail=str(exc),
                ),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/stops", response_model=PositionView)
    async def stops(
        payload: StopsRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> PositionView:
        try:
            response = await service.apply_stops(db, payload)
            log_event(
                "trade.stops",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    stop_mode=payload.stopMode,
                    outcome="success",
                ),
            )
            return response
        except ValueError as exc:
            log_event(
                "trade.stops",
                level="warning",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    stop_mode=payload.stopMode,
                    outcome="error",
                    detail=str(exc),
                ),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profit", response_model=PositionView)
    async def profit(
        payload: ProfitRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> PositionView:
        try:
            response = await service.execute_profit_plan(db, payload)
            log_event(
                "trade.profit",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    tranche_count=len(payload.trancheModes),
                    outcome="success",
                ),
            )
            return response
        except ValueError as exc:
            log_event(
                "trade.profit",
                level="warning",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    tranche_count=len(payload.trancheModes),
                    outcome="error",
                    detail=str(exc),
                ),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/flatten", response_model=PositionView)
    async def flatten(
        payload: MoveToBeRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> PositionView:
        try:
            response = await service.flatten(db, payload.symbol)
            log_event(
                "trade.flatten",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    outcome="success",
                ),
            )
            return response
        except ValueError as exc:
            log_event(
                "trade.flatten",
                level="warning",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    outcome="error",
                    detail=str(exc),
                ),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/move_to_be", response_model=PositionView)
    async def move_to_be(
        payload: MoveToBeRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_write_guard),
    ) -> PositionView:
        try:
            response = await service.move_to_be(db, payload.symbol)
            log_event(
                "trade.move_to_be",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    outcome="success",
                ),
            )
            return response
        except ValueError as exc:
            log_event(
                "trade.move_to_be",
                level="warning",
                **request_log_fields(
                    request,
                    username=str(session["user"]["username"]),
                    symbol=payload.symbol.upper(),
                    outcome="error",
                    detail=str(exc),
                ),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
