from __future__ import annotations

import hmac
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


def require_trusted_origin(request: Request) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if not origin:
        return
    if origin not in settings.trusted_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


def require_csrf(request: Request) -> None:
    if not settings.auth_require_csrf:
        return
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
    header_token = request.headers.get(settings.auth_csrf_header_name)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )


def require_write_guard(request: Request, _: dict[str, Any] = Depends(require_session)) -> None:
    require_trusted_origin(request)
    require_csrf(request)


def require_webhook_secret(request: Request) -> None:
    expected = settings.ops_signing_secret.strip()
    if not expected:
        if settings.app_env in {"staging", "production"}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook signing secret is not configured",
            )
        return
    provided = request.headers.get(settings.webhook_secret_header_name, "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )


def require_operator_session(
    session: dict[str, Any] = Depends(require_session),
) -> dict[str, Any]:
    if settings.require_ops_auth and str(session["user"]["role"]) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin session required")
    return session


async def require_websocket_session(websocket: WebSocket) -> dict[str, Any]:
    session = resolve_session_from_cookie(websocket.cookies.get(settings.auth_cookie_name))
    if session is None:
        await websocket.close(code=4401, reason="Not authenticated")
        raise RuntimeError("Websocket session required")
    return session
