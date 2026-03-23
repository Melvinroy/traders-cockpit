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
    if not settings.uses_database_auth_storage:
        issues.append("Hosted startup requires AUTH_STORAGE_MODE=database.")
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


def check_auth_path(path_value: str) -> str | None:
    try:
        ensure_auth_db_path(path_value)
    except OSError as exc:
        return f"auth path unavailable: {exc}"
    return None


def check_database(database_url: str) -> str | None:
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - exercised through readiness tests
        return f"database unavailable: {exc}"
    finally:
        engine.dispose()
    return None


def check_redis(redis_url: str) -> str | None:
    client = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        client.ping()
    except Exception as exc:  # pragma: no cover - exercised through readiness tests
        return f"redis unavailable: {exc}"
    finally:
        client.close()
    return None


def build_liveness_report(settings: Settings) -> dict[str, object]:
    return {
        "status": "ok",
        "kind": "live",
        "app_env": settings.app_env,
        "broker_mode": settings.broker_mode,
    }


def build_dependency_report(settings: Settings) -> dict[str, dict[str, str]]:
    dependencies: dict[str, dict[str, str]] = {}
    db_issue: str | None = None

    if settings.app_env in HOSTED_ENVS or settings.uses_database_auth_storage:
        db_issue = check_database(settings.database_url)
        dependencies["database"] = {"status": "ok" if db_issue is None else "error"}
        if db_issue is not None:
            dependencies["database"]["detail"] = db_issue

    if settings.uses_database_auth_storage:
        auth_issue = None if db_issue is None else f"database-backed auth unavailable: {db_issue}"
        dependencies["auth"] = {
            "status": "ok" if auth_issue is None else "error",
            "mode": "database",
        }
    else:
        auth_issue = check_auth_path(settings.auth_db_path)
        dependencies["auth"] = {
            "status": "ok" if auth_issue is None else "error",
            "mode": "file",
        }
    if auth_issue is not None:
        dependencies["auth"]["detail"] = auth_issue

    if settings.app_env in HOSTED_ENVS:
        redis_issue = check_redis(settings.redis_url)
        dependencies["redis"] = {"status": "ok" if redis_issue is None else "error"}
        if redis_issue is not None:
            dependencies["redis"]["detail"] = redis_issue

    return dependencies


def build_readiness_report(settings: Settings) -> dict[str, object]:
    runtime_issues = validate_runtime_contract(settings)
    dependencies = build_dependency_report(settings)
    dependency_failures = [
        name for name, payload in dependencies.items() if payload.get("status") != "ok"
    ]
    status = "ok" if not runtime_issues and not dependency_failures else "error"
    report: dict[str, object] = {
        "status": status,
        "kind": "ready",
        "app_env": settings.app_env,
        "broker_mode": settings.broker_mode,
        "runtime_contract": {
            "status": "ok" if not runtime_issues else "error",
            "issues": runtime_issues,
        },
        "dependencies": dependencies,
    }
    return report


def run_startup_preflight(settings: Settings) -> None:
    readiness = build_readiness_report(settings)
    if readiness["status"] == "ok":
        return

    runtime_issues = readiness["runtime_contract"]["issues"]
    dependency_issues = [
        payload["detail"]
        for payload in readiness["dependencies"].values()
        if payload.get("status") != "ok" and "detail" in payload
    ]
    joined = "\n".join(f"- {issue}" for issue in [*runtime_issues, *dependency_issues])
    raise RuntimeError(f"Startup preflight failed:\n{joined}")


def main() -> None:
    settings = Settings.from_env()
    run_startup_preflight(settings)
    print("Startup preflight passed")


if __name__ == "__main__":
    main()
