from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import require_session
from app.db.session import get_db
from app.schemas.cockpit import SetupResponse
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["market"], dependencies=[Depends(require_session)])

    @router.get("/setup/{symbol}", response_model=SetupResponse)
    def get_setup(symbol: str, db: Session = Depends(get_db)) -> SetupResponse:
        try:
            return service.get_setup(db, symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
