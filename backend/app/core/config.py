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


@dataclass
class Settings:
    app_env: str
    auth_require_login: bool
    auth_session_ttl_hours: int
    auth_cookie_name: str
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
        sqlite_fallback_url = os.getenv("SQLITE_FALLBACK_URL", "sqlite:///./data/traders_cockpit.db").strip()
        allow_sqlite_fallback = _as_bool(os.getenv("ALLOW_SQLITE_FALLBACK", "false"))
        default_db = (
            sqlite_fallback_url
            if app_env == "test" or allow_sqlite_fallback
            else "postgresql://traders_cockpit:traders_cockpit@127.0.0.1:55432/traders_cockpit"
        )
        return cls(
            app_env=app_env,
            auth_require_login=_as_bool(os.getenv("AUTH_REQUIRE_LOGIN", "true"), True),
            auth_session_ttl_hours=max(1, int(os.getenv("AUTH_SESSION_TTL_HOURS", "24"))),
            auth_cookie_name=os.getenv("AUTH_COOKIE_NAME", "traders_cockpit_session").strip(),
            auth_seed_users=_as_bool(os.getenv("AUTH_SEED_USERS", "true"), True),
            auth_admin_username=os.getenv("AUTH_ADMIN_USERNAME", "admin").strip(),
            auth_admin_password=os.getenv("AUTH_ADMIN_PASSWORD", "admin123!").strip(),
            auth_trader_username=os.getenv("AUTH_TRADER_USERNAME", "trader").strip(),
            auth_trader_password=os.getenv("AUTH_TRADER_PASSWORD", "trader123!").strip(),
            database_url=os.getenv("DATABASE_URL", default_db).strip(),
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
    def live_trading_enabled(self) -> bool:
        return self.broker_mode == "alpaca_live" and self.allow_live_trading and bool(self.live_confirmation_token)
