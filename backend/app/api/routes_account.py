from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import require_operator_session, require_session, require_write_guard
from app.db.session import get_db
from app.schemas.cockpit import AccountSettingsUpdate, AccountSettingsView, LogEntry
from app.services.cockpit import CockpitService


def build_router(service: CockpitService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["account"], dependencies=[Depends(require_session)])

    @router.get("/account", response_model=AccountSettingsView)
    def get_account(db: Session = Depends(get_db)) -> AccountSettingsView:
        return service.get_account(db)

    @router.put("/account/settings", response_model=AccountSettingsView)
    async def update_account(
        payload: AccountSettingsUpdate,
        db: Session = Depends(get_db),
        _: dict = Depends(require_operator_session),
        __: None = Depends(require_write_guard),
    ) -> AccountSettingsView:
        try:
            view = service.update_account(db, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await service.broadcast_account_update(db)
        return view

    @router.get("/activity-log", response_model=list[LogEntry])
    def get_logs(db: Session = Depends(get_db)) -> list[LogEntry]:
        return service.get_logs(db)

    @router.delete("/activity-log")
    def clear_logs(
        db: Session = Depends(get_db), _: None = Depends(require_write_guard)
    ) -> dict[str, int]:
        return {"cleared": service.clear_logs(db)}

    return router
