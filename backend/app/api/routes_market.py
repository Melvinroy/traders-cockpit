from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cockpit import SetupResponse
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["market"])

    @router.get("/setup/{symbol}", response_model=SetupResponse)
    def get_setup(symbol: str, db: Session = Depends(get_db)) -> SetupResponse:
        return service.get_setup(db, symbol)

    return router
