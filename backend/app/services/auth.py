from __future__ import annotations

from app.core.config import Settings


def authenticate_user(settings: Settings, username: str, password: str) -> dict | None:
    if username == settings.auth_admin_username and password == settings.auth_admin_password:
        return {"username": username, "role": "admin"}
    if username == settings.auth_trader_username and password == settings.auth_trader_password:
        return {"username": username, "role": "trader"}
    return None
