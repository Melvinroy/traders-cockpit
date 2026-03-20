from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import Settings
from app.schemas.cockpit import LoginRequest, LoginResponse
from app.services.auth import authenticate_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = Settings.from_env()


@router.get("/me", response_model=LoginResponse)
def me(request: Request) -> LoginResponse:
    username = request.cookies.get(settings.auth_cookie_name)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role = "admin" if username == settings.auth_admin_username else "trader"
    return LoginResponse(username=username, role=role)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response) -> LoginResponse:
    user = authenticate_user(settings, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response.set_cookie(
        settings.auth_cookie_name,
        user["username"],
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )
    return LoginResponse(**user)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(settings.auth_cookie_name)
    return {"ok": True}
