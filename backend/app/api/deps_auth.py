from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, WebSocket, status

from app.core.config import Settings
from app.services.auth import get_auth_store

settings = Settings.from_env()
auth_store = get_auth_store(settings)


def _default_user() -> dict[str, Any]:
    username = (
        settings.auth_admin_username
        if settings.app_default_role == "admin"
        else settings.auth_trader_username
    )
    return {
        "user": {
            "id": 0,
            "username": username,
            "role": settings.app_default_role,
        },
        "expires_at": None,
    }


def resolve_session_from_cookie(session_token: str | None) -> dict[str, Any] | None:
    if not settings.auth_require_login and not session_token:
        return _default_user()
    return auth_store.resolve_session(session_token=session_token)


def require_session(request: Request) -> dict[str, Any]:
    session = resolve_session_from_cookie(request.cookies.get(settings.auth_cookie_name))
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return session


def require_operator_session(session: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
    if settings.require_ops_auth and str(session["user"]["role"]) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin session required")
    return session


async def require_websocket_session(websocket: WebSocket) -> dict[str, Any]:
    session = resolve_session_from_cookie(websocket.cookies.get(settings.auth_cookie_name))
    if session is None:
        await websocket.close(code=4401, reason="Not authenticated")
        raise RuntimeError("Websocket session required")
    return session
