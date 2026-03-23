from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.config import Settings
from app.db.base import Base
from app.services.auth import (
    FAILED_LOGIN_LIMIT,
    DatabaseAuthStore,
    FileAuthStore,
    clear_auth_store_cache,
    get_auth_store,
)


@pytest.fixture(autouse=True)
def reset_auth_store_cache() -> None:
    clear_auth_store_cache()
    yield
    clear_auth_store_cache()


def test_staging_defaults_to_database_auth_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("AUTH_STORAGE_MODE", raising=False)

    settings = Settings.from_env()

    assert settings.auth_storage_mode == "database"
    assert settings.uses_database_auth_storage is True


def test_get_auth_store_uses_file_storage_for_local_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_STORAGE_MODE", "file")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))

    store = get_auth_store(Settings.from_env())

    assert isinstance(store, FileAuthStore)


def test_get_auth_store_uses_database_storage_and_persists_sessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "auth-store.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_STORAGE_MODE", "database")
    monkeypatch.delenv("AUTH_DB_PATH", raising=False)

    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()

    store = get_auth_store(Settings.from_env())
    assert isinstance(store, DatabaseAuthStore)

    store.bootstrap_users(
        admin_username="admin",
        admin_password="change-me-admin",
        trader_username="trader",
        trader_password="change-me-trader",
        seed_enabled=True,
    )
    user = store.authenticate(username="admin", password="change-me-admin")
    assert user is not None

    session_token, session_data = store.create_session(
        user=user,
        user_agent="pytest",
        ip_addr="127.0.0.1",
    )
    resolved = store.resolve_session(session_token=session_token)
    assert resolved is not None
    assert resolved["user"]["username"] == "admin"
    assert resolved["expires_at"] != session_data["expires_at"]

    for _ in range(FAILED_LOGIN_LIMIT):
        allowed, retry_after = store.record_login_failure(username="admin", ip_addr="127.0.0.1")
        assert allowed is True
        assert retry_after is None

    allowed, retry_after = store.record_login_failure(username="admin", ip_addr="127.0.0.1")
    assert allowed is False
    assert retry_after is not None

    store.clear_login_failures(username="admin", ip_addr="127.0.0.1")
    allowed, retry_after = store.check_login_allowed(username="admin", ip_addr="127.0.0.1")
    assert allowed is True
    assert retry_after is None
