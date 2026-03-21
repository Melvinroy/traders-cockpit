from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import Settings
from app.schemas.cockpit import LoginRequest, LoginResponse
from app.services.auth import get_auth_store

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = Settings.from_env()
auth_store = get_auth_store(settings)


@router.get("/me", response_model=LoginResponse)
def me(request: Request) -> LoginResponse:
    session_token = request.cookies.get(settings.auth_cookie_name)
    session = auth_store.resolve_session(session_token=session_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return LoginResponse(
        username=str(session["user"]["username"]),
        role=str(session["user"]["role"]),
        expires_at=str(session["expires_at"]),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    user = auth_store.authenticate(username=payload.username, password=payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    session_token, session_data = auth_store.create_session(
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_addr=request.client.host if request.client else None,
    )
    response.set_cookie(
        settings.auth_cookie_name,
        session_token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )
    return LoginResponse(
        username=user.username,
        role=user.role,
        expires_at=str(session_data["expires_at"]),
    )


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    auth_store.revoke_session(session_token=request.cookies.get(settings.auth_cookie_name))
    response.delete_cookie(settings.auth_cookie_name)
    return {"ok": True}
