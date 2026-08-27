# Environment contract

This reference complements the README and documents the runtime configuration keys enforced by `scripts/dev/check-config-contract.py`.

## Authentication and request safety

- `AUTH_COOKIE_NAME` — session cookie name.
- `AUTH_STORAGE_MODE` — `file` for local development or `database` for hosted environments.
- `AUTH_DB_PATH` — local auth database path when file storage is used.
- `AUTH_SEED_USERS` — whether local seed users are created.
- `AUTH_TRADER_PASSWORD` — seeded trader password for local-only environments; replace placeholder values outside local development.
- `AUTH_CSRF_HEADER_NAME` — request header used for CSRF token validation.
- `AUTH_CSRF_COOKIE_NAME` — browser cookie used for CSRF token validation.
- `AUTH_REQUIRE_CSRF` — enables CSRF validation for state-changing requests.
- `TRUSTED_ORIGINS` — browser origins allowed to perform trusted state-changing requests.
- `WEBHOOK_SECRET_HEADER_NAME` — header containing the webhook signing secret.

## Trading and reconciliation safety

- `TRADING_ENABLED` — master trading enable/disable switch.
- `DISABLED_SYMBOLS` — comma-separated symbols blocked from trading.
- `MAX_QUOTE_AGE_SECONDS` — maximum accepted quote age.
- `RECONCILE_FAST_INTERVAL_SECONDS` — fast reconciliation interval.
- `RECONCILE_SLOW_INTERVAL_SECONDS` — slow reconciliation interval.
- `MAX_RECONCILE_AGE_SECONDS` — maximum reconciliation age before state is treated as stale.

The canonical templates remain `.env.example` for deterministic local development and `.env.production.example` for hosted environments. Both templates intentionally carry the same key set, with environment-appropriate values.
