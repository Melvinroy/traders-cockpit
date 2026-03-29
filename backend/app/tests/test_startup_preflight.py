from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.startup_preflight import (
    build_dependency_report,
    build_readiness_report,
    ensure_auth_db_path,
    validate_runtime_contract,
)


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "development",
        "app_default_role": "admin",
        "allow_app_role_override": True,
        "require_ops_auth": False,
        "auth_require_login": True,
        "auth_session_ttl_hours": 24,
        "auth_cookie_name": "traders_cockpit_session",
        "auth_cookie_samesite": "lax",
        "auth_cookie_secure": False,
        "auth_storage_mode": "file",
        "auth_csrf_cookie_name": "traders_cockpit_csrf",
        "auth_csrf_header_name": "X-CSRF-Token",
        "auth_require_csrf": False,
        "webhook_secret_header_name": "X-Webhook-Secret",
        "auth_db_path": "./data/auth.db",
        "auth_seed_users": True,
        "auth_admin_username": "admin",
        "auth_admin_password": "change-me-admin",
        "auth_trader_username": "trader",
        "auth_trader_password": "change-me-trader",
        "database_url": "postgresql+psycopg://user:pass@db:5432/traders_cockpit",
        "redis_url": "redis://redis:6379/0",
        "redis_channel_prefix": "traders-cockpit",
        "cors_origins": ["https://app.example.com"],
        "trusted_origins": ["https://app.example.com"],
        "broker_mode": "paper",
        "allow_live_trading": False,
        "allow_controller_mock": False,
        "live_confirmation_token": "",
        "alpaca_api_key_id": "",
        "alpaca_api_secret_key": "",
        "alpaca_api_base_url": "https://paper-api.alpaca.markets",
        "alpaca_live_api_base_url": "https://api.alpaca.markets",
        "alpaca_data_base_url": "https://data.alpaca.markets",
        "massive_api_key": "",
        "massive_api_base_url": "https://api.polygon.io",
        "default_account_equity": 100000.0,
        "default_risk_pct": 1.0,
        "max_position_notional_pct": 100.0,
        "daily_loss_limit_pct": 2.0,
        "max_open_positions": 6,
        "trading_enabled": True,
        "disabled_symbols": [],
        "max_quote_age_seconds": 15,
        "reconcile_fast_interval_seconds": 3,
        "reconcile_slow_interval_seconds": 20,
        "max_reconcile_age_seconds": 45,
        "ops_api_key": "",
        "ops_admin_api_key": "",
        "ops_signing_secret": "",
        "sqlite_fallback_url": "sqlite:///./data/traders_cockpit.db",
        "allow_sqlite_fallback": False,
    }
    base.update(overrides)
    return Settings(**base)


def test_validate_runtime_contract_allows_local_defaults() -> None:
    issues = validate_runtime_contract(make_settings())
    assert issues == []


def test_validate_runtime_contract_rejects_hosted_sqlite_and_insecure_auth() -> None:
    settings = make_settings(
        app_env="production",
        auth_storage_mode="database",
        allow_sqlite_fallback=True,
        database_url="sqlite:///./data/traders_cockpit.db",
        auth_cookie_secure=False,
        require_ops_auth=False,
    )
    issues = validate_runtime_contract(settings)

    assert any("SQLite" in issue for issue in issues)
    assert any("AUTH_COOKIE_SECURE=true" in issue for issue in issues)
    assert any("OPS_REQUIRE_AUTH=true" in issue for issue in issues)


def test_validate_runtime_contract_rejects_hosted_file_auth() -> None:
    settings = make_settings(
        app_env="staging",
        auth_storage_mode="file",
        auth_cookie_secure=True,
        require_ops_auth=True,
    )

    issues = validate_runtime_contract(settings)

    assert any("AUTH_STORAGE_MODE=database" in issue for issue in issues)


def test_ensure_auth_db_path_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "auth.db"

    resolved = ensure_auth_db_path(str(target))

    assert resolved == target
    assert target.parent.is_dir()
    assert target.exists()


def test_build_readiness_report_marks_local_settings_ready(tmp_path: Path) -> None:
    settings = make_settings(auth_db_path=str(tmp_path / "auth.db"))

    report = build_readiness_report(settings)

    assert report["status"] == "ok"
    assert report["kind"] == "ready"
    assert report["runtime_contract"]["status"] == "ok"
    assert report["dependencies"]["auth"]["status"] == "ok"


def test_build_dependency_report_includes_hosted_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(app_env="staging", auth_storage_mode="database")
    monkeypatch.setattr(
        "app.core.startup_preflight.check_database",
        lambda database_url: None,
    )
    monkeypatch.setattr(
        "app.core.startup_preflight.check_redis",
        lambda redis_url: "redis unavailable",
    )

    report = build_dependency_report(settings)

    assert report["database"]["status"] == "ok"
    assert report["redis"]["status"] == "error"
    assert report["redis"]["detail"] == "redis unavailable"
    assert report["auth"]["status"] == "ok"
    assert report["auth"]["mode"] == "database"


def test_build_dependency_report_uses_file_auth_for_local_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(auth_storage_mode="file")
    monkeypatch.setattr(
        "app.core.startup_preflight.check_auth_path",
        lambda path_value: None,
    )

    report = build_dependency_report(settings)

    assert report["auth"]["status"] == "ok"
    assert report["auth"]["mode"] == "file"
    assert "database" not in report
