# Hosted Deployment

Hosted deployment is a trailing deliverable. Validate the local paper-trading path first, then redeploy hosted staging from a known-good local state.

Use `.env.production.example` as the public hosted config contract. Copy it to a private env file, fill in real values, and keep `.env.example` reserved for deterministic local development.

## Recommended Topology

- Frontend: Vercel
- Backend: Render web service or any Docker-capable container host
- PostgreSQL: managed Postgres
- Redis: managed Redis

## Frontend

Deploy the `frontend/` directory as a Next.js project.

Required frontend envs:

- `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-host>`
- `NEXT_PUBLIC_WS_URL=wss://<your-backend-host>/ws/cockpit`

Important:

- The frontend is not useful without a reachable public backend URL.
- Do not point a hosted frontend at `127.0.0.1`.

## Backend

Use [backend/Dockerfile](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/backend/Dockerfile).

Startup behavior:

- runs `alembic upgrade head`
- starts `uvicorn`
- exposes:
  - `/health/live` for liveness
  - `/health/ready` for readiness
  - `/health/deps` for dependency detail

Required backend envs:

- `APP_ENV=staging` or `production`
- `DATABASE_URL`
- `REDIS_URL`
- `CORS_ORIGINS`
- `AUTH_COOKIE_SECURE=true`
- `AUTH_COOKIE_SAMESITE=none` for cross-origin frontend/backends
- `AUTH_STORAGE_MODE=database`
- `AUTH_ADMIN_USERNAME`
- `AUTH_ADMIN_PASSWORD`
- `AUTH_TRADER_USERNAME`
- `AUTH_TRADER_PASSWORD`

Optional but recommended:

- `REDIS_CHANNEL_PREFIX`
- `OPS_API_KEY`
- `OPS_ADMIN_API_KEY`
- `OPS_SIGNING_SECRET`
- Alpaca/Polygon credentials when using live external providers

## Render Blueprint

The repo includes [render.yaml](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/render.yaml) for:

- backend web service
- managed Postgres
- managed Redis

The current Render blueprint keeps hosted auth inside the primary database by setting `AUTH_STORAGE_MODE=database`. Keep the hosted env file aligned with `.env.production.example`.

After backend deployment, copy the public backend origin into:

- Vercel `NEXT_PUBLIC_API_BASE_URL`
- Vercel `NEXT_PUBLIC_WS_URL`
- backend `CORS_ORIGINS`

Keep these origin groups explicit:

- dev: `http://127.0.0.1:3000`, `http://127.0.0.1:3010`
- hosted preview: your preview frontend origin
- hosted production: your production frontend origin

## Pre-Deploy Validation

Validate a staged env file locally with:

```powershell
Copy-Item .env.production.example .env.production.local
# edit .env.production.local
.\scripts\dev\check-hosted-env.ps1 -EnvFile ".env.production.local"
```

The hosted env check now rejects:

- localhost / `127.0.0.1` public URLs
- SQLite-backed hosted config
- file-backed hosted auth config
- insecure auth cookie settings
- missing live confirmation token when live trading is enabled

## Hosted Smoke

After the hosted backend and frontend are deployed, run the browser smoke against the real URLs:

```powershell
Copy-Item .env.production.example .env.production.local
# Edit .env.production.local with the hosted admin credentials
.\scripts\dev\run-hosted-smoke.ps1 `
  -FrontendUrl "https://app.example.com" `
  -BackendUrl "https://api.example.com" `
  -EnvFile ".env.production.local"
```

For local validation of the wrapper against a non-hosted stack, you can override the auth credentials explicitly:

```powershell
.\scripts\dev\run-hosted-smoke.ps1 `
  -FrontendUrl "http://127.0.0.1:3094" `
  -BackendUrl "http://127.0.0.1:8094" `
  -EnvFile ".env.production.example" `
  -AuthUsername "admin" `
  -AuthPassword "change-me-admin"
```

Expected artifacts:

- `frontend/output/playwright/hosted-smoke.png`
- `frontend/output/playwright/hosted-smoke.console.txt`
- `frontend/output/playwright/hosted-smoke.network.txt`

The hosted smoke reuses the same login and setup-load browser path as the local smoke flow, but points it at the hosted frontend/backend pair you provide.

## Hosted Auth Persistence

Hosted auth now uses the primary database rather than a mounted disk:

- `AUTH_STORAGE_MODE=database`
- auth users, sessions, and login attempts live in Postgres

Local development can still use `AUTH_STORAGE_MODE=file` with `AUTH_DB_PATH`, but hosted staging and production should keep auth on the primary database.

## Promotion Path

1. Deploy backend staging.
2. Confirm `/health/live` and `/health/ready` both work.
3. Configure frontend public envs.
4. Deploy frontend preview/staging.
5. Run browser smoke against hosted URLs.
6. Promote only after hosted smoke passes.
