from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cockpit import AccountSettingsUpdate, AccountSettingsView, LogEntry
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["account"])

    @router.get("/account", response_model=AccountSettingsView)
    def get_account(db: Session = Depends(get_db)) -> AccountSettingsView:
        return service.get_account(db)

    @router.put("/account/settings", response_model=AccountSettingsView)
    def update_account(payload: AccountSettingsUpdate, db: Session = Depends(get_db)) -> AccountSettingsView:
        return service.update_account(db, payload)

    @router.get("/activity-log", response_model=list[LogEntry])
    def get_logs(db: Session = Depends(get_db)) -> list[LogEntry]:
        return service.get_logs(db)

    return router
