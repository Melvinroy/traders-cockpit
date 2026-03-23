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

Required backend envs:

- `APP_ENV=staging` or `production`
- `DATABASE_URL`
- `REDIS_URL`
- `CORS_ORIGINS`
- `AUTH_COOKIE_SECURE=true`
- `AUTH_COOKIE_SAMESITE=none` for cross-origin frontend/backends
- `AUTH_DB_PATH` on a persistent disk path
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

Treat the current Render blueprint as a staging starting point. Before using it as a production contract, add an explicit persistent path for `AUTH_DB_PATH` and keep the hosted env file aligned with `.env.production.example`.

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
- insecure auth cookie settings
- missing live confirmation token when live trading is enabled

## Promotion Path

1. Deploy backend staging.
2. Confirm `/health` works.
3. Configure frontend public envs.
4. Deploy frontend preview/staging.
5. Run browser smoke against hosted URLs.
6. Promote only after hosted smoke passes.
