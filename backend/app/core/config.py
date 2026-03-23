from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_key = key.strip()
        if not env_key or env_key in os.environ:
            continue
        os.environ[env_key] = value.strip().strip("'").strip('"')


def _bootstrap_env() -> None:
    module_dir = Path(__file__).resolve().parent
    backend_dir = module_dir.parent.parent
    cwd = Path.cwd()
    for candidate in [cwd / ".env", backend_dir / ".env", backend_dir.parent / ".env"]:
        _load_env_file(candidate)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_database_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


@dataclass
class Settings:
    app_env: str
    app_default_role: str
    allow_app_role_override: bool
    require_ops_auth: bool
    auth_require_login: bool
    auth_session_ttl_hours: int
    auth_cookie_name: str
    auth_cookie_samesite: str
    auth_cookie_secure: bool
    auth_db_path: str
    auth_seed_users: bool
    auth_admin_username: str
    auth_admin_password: str
    auth_trader_username: str
    auth_trader_password: str
    database_url: str
    redis_url: str
    redis_channel_prefix: str
    cors_origins: list[str]
    broker_mode: str
    allow_live_trading: bool
    allow_controller_mock: bool
    live_confirmation_token: str
    alpaca_api_key_id: str
    alpaca_api_secret_key: str
    alpaca_api_base_url: str
    alpaca_live_api_base_url: str
    alpaca_data_base_url: str
    massive_api_key: str
    massive_api_base_url: str
    default_account_equity: float
    default_risk_pct: float
    max_position_notional_pct: float
    daily_loss_limit_pct: float
    max_open_positions: int
    ops_api_key: str
    ops_admin_api_key: str
    ops_signing_secret: str
    sqlite_fallback_url: str
    allow_sqlite_fallback: bool

    @classmethod
    def from_env(cls) -> "Settings":
        _bootstrap_env()
        app_env_raw = os.getenv("APP_ENV", "development").strip().lower()
        app_env = {
            "prod": "production",
            "production": "production",
            "stage": "staging",
            "staging": "staging",
            "test": "test",
            "testing": "test",
        }.get(app_env_raw, "development")
        app_default_role_raw = os.getenv("APP_DEFAULT_ROLE", "admin").strip().lower()
        app_default_role = (
            app_default_role_raw if app_default_role_raw in {"admin", "trader"} else "admin"
        )
        allow_role_override_default = "false" if app_env == "production" else "true"
        allow_role_override = _as_bool(
            os.getenv("APP_ALLOW_ROLE_OVERRIDE", allow_role_override_default)
        )
        require_ops_auth_default = "true" if app_env == "production" else "false"
        require_ops_auth = _as_bool(os.getenv("OPS_REQUIRE_AUTH", require_ops_auth_default))
        sqlite_fallback_url = os.getenv(
            "SQLITE_FALLBACK_URL", "sqlite:///./data/traders_cockpit.db"
        ).strip()
        allow_sqlite_fallback = _as_bool(os.getenv("ALLOW_SQLITE_FALLBACK", "false"))
        auth_db_path = os.getenv("AUTH_DB_PATH", "./data/auth.db").strip() or "./data/auth.db"
        auth_cookie_secure_default = "true" if app_env in {"staging", "production"} else "false"
        auth_cookie_samesite_default = "none" if app_env in {"staging", "production"} else "lax"
        auth_cookie_samesite_raw = (
            os.getenv("AUTH_COOKIE_SAMESITE", auth_cookie_samesite_default).strip().lower()
        )
        auth_cookie_samesite = (
            auth_cookie_samesite_raw
            if auth_cookie_samesite_raw in {"lax", "strict", "none"}
            else auth_cookie_samesite_default
        )
        default_db = (
            sqlite_fallback_url
            if app_env == "test" or allow_sqlite_fallback
            else "postgresql://traders_cockpit:change-me-postgres@127.0.0.1:55432/traders_cockpit"
        )
        return cls(
            app_env=app_env,
            app_default_role=app_default_role,
            allow_app_role_override=allow_role_override,
            require_ops_auth=require_ops_auth,
            auth_require_login=_as_bool(os.getenv("AUTH_REQUIRE_LOGIN", "true"), True),
            auth_session_ttl_hours=max(1, int(os.getenv("AUTH_SESSION_TTL_HOURS", "24"))),
            auth_cookie_name=os.getenv("AUTH_COOKIE_NAME", "traders_cockpit_session").strip(),
            auth_cookie_samesite=auth_cookie_samesite,
            auth_cookie_secure=_as_bool(
                os.getenv("AUTH_COOKIE_SECURE", auth_cookie_secure_default)
            ),
            auth_db_path=auth_db_path,
            auth_seed_users=_as_bool(os.getenv("AUTH_SEED_USERS", "true"), True),
            auth_admin_username=os.getenv("AUTH_ADMIN_USERNAME", "admin").strip(),
            auth_admin_password=os.getenv("AUTH_ADMIN_PASSWORD", "change-me-admin").strip(),
            auth_trader_username=os.getenv("AUTH_TRADER_USERNAME", "trader").strip(),
            auth_trader_password=os.getenv("AUTH_TRADER_PASSWORD", "change-me-trader").strip(),
            database_url=_normalize_database_url(os.getenv("DATABASE_URL", default_db)),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:56379/0").strip(),
            redis_channel_prefix=os.getenv("REDIS_CHANNEL_PREFIX", "traders-cockpit").strip(),
            cors_origins=[
                item.strip()
                for item in os.getenv(
                    "CORS_ORIGINS",
                    "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:3010,http://localhost:3010",
                ).split(",")
                if item.strip()
            ],
            broker_mode=os.getenv("BROKER_MODE", "paper").strip().lower(),
            allow_live_trading=_as_bool(os.getenv("ALLOW_LIVE_TRADING", "false")),
            allow_controller_mock=_as_bool(os.getenv("ALLOW_CONTROLLER_MOCK", "true"), True),
            live_confirmation_token=os.getenv("LIVE_CONFIRMATION_TOKEN", "").strip(),
            alpaca_api_key_id=os.getenv("ALPACA_API_KEY_ID", "").strip(),
            alpaca_api_secret_key=os.getenv("ALPACA_API_SECRET_KEY", "").strip(),
            alpaca_api_base_url=os.getenv(
                "ALPACA_API_BASE_URL", "https://paper-api.alpaca.markets"
            ).strip(),
            alpaca_live_api_base_url=os.getenv(
                "ALPACA_LIVE_API_BASE_URL", "https://api.alpaca.markets"
            ).strip(),
            alpaca_data_base_url=os.getenv(
                "ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"
            ).strip(),
            massive_api_key=os.getenv("MASSIVE_API_KEY", "") or os.getenv("POLYGON_API_KEY", ""),
            massive_api_base_url=os.getenv(
                "MASSIVE_API_BASE_URL", os.getenv("POLYGON_API_BASE_URL", "https://api.polygon.io")
            ).strip(),
            default_account_equity=float(os.getenv("DEFAULT_ACCOUNT_EQUITY", "100000")),
            default_risk_pct=float(os.getenv("DEFAULT_RISK_PCT", "1")),
            max_position_notional_pct=float(os.getenv("MAX_POSITION_NOTIONAL_PCT", "100")),
            daily_loss_limit_pct=float(os.getenv("DAILY_LOSS_LIMIT_PCT", "2")),
            max_open_positions=max(1, int(os.getenv("MAX_OPEN_POSITIONS", "6"))),
            ops_api_key=os.getenv("OPS_API_KEY", "").strip(),
            ops_admin_api_key=os.getenv("OPS_ADMIN_API_KEY", "").strip(),
            ops_signing_secret=os.getenv("OPS_SIGNING_SECRET", "").strip(),
            sqlite_fallback_url=sqlite_fallback_url,
            allow_sqlite_fallback=allow_sqlite_fallback,
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def has_alpaca_credentials(self) -> bool:
        return bool(self.alpaca_api_key_id and self.alpaca_api_secret_key)

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def uses_alpaca_broker(self) -> bool:
        return self.broker_mode in {"alpaca_paper", "alpaca_live"}

    @property
    def broker_execution_provider(self) -> str:
        if self.uses_alpaca_broker and self.has_alpaca_credentials:
            return self.broker_mode
        return "paper"

    @property
    def local_personal_paper_ready(self) -> bool:
        return (
            self.broker_mode == "alpaca_paper"
            and not self.allow_live_trading
            and self.has_alpaca_credentials
        )

    @property
    def live_trading_enabled(self) -> bool:
        return (
            self.broker_mode == "alpaca_live"
            and self.allow_live_trading
            and bool(self.live_confirmation_token)
        )
