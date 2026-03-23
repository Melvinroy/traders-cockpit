from __future__ import annotations

from pathlib import Path

from redis import Redis
from sqlalchemy import create_engine

from app.core.config import Settings

HOSTED_ENVS = {"staging", "production"}


def validate_runtime_contract(settings: Settings) -> list[str]:
    issues: list[str] = []
    if settings.app_env not in HOSTED_ENVS:
        return issues

    if settings.allow_sqlite_fallback or settings.uses_sqlite:
        issues.append("Hosted startup requires PostgreSQL; SQLite fallback must stay disabled.")
    if not settings.auth_require_login:
        issues.append("Hosted startup requires AUTH_REQUIRE_LOGIN=true.")
    if not settings.auth_cookie_secure:
        issues.append("Hosted startup requires AUTH_COOKIE_SECURE=true.")
    if settings.app_env == "production" and settings.allow_app_role_override:
        issues.append("Production startup requires APP_ALLOW_ROLE_OVERRIDE=false.")
    if settings.app_env == "production" and not settings.require_ops_auth:
        issues.append("Production startup requires OPS_REQUIRE_AUTH=true.")
    if settings.allow_live_trading and not settings.live_trading_enabled:
        issues.append("ALLOW_LIVE_TRADING is set but the live confirmation contract is incomplete.")

    return issues


def ensure_auth_db_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8"):
        pass
    return path


def check_database(database_url: str) -> None:
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    finally:
        engine.dispose()


def check_redis(redis_url: str) -> None:
    client = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        client.ping()
    finally:
        client.close()


def run_startup_preflight(settings: Settings) -> None:
    issues = validate_runtime_contract(settings)
    if issues:
        joined = "\n".join(f"- {issue}" for issue in issues)
        raise RuntimeError(f"Startup preflight failed:\n{joined}")

    ensure_auth_db_path(settings.auth_db_path)
    if settings.app_env in HOSTED_ENVS:
        check_database(settings.database_url)
        check_redis(settings.redis_url)


def main() -> None:
    settings = Settings.from_env()
    run_startup_preflight(settings)
    print("Startup preflight passed")


if __name__ == "__main__":
    main()
