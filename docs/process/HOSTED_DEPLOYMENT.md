# Hosted Deployment

Hosted deployment is a trailing deliverable. Validate the local paper-trading path first, then redeploy hosted staging from a known-good local state.

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

After backend deployment, copy the public backend origin into:

- Vercel `NEXT_PUBLIC_API_BASE_URL`
- Vercel `NEXT_PUBLIC_WS_URL`
- backend `CORS_ORIGINS`

## Pre-Deploy Validation

Validate a staged env file locally with:

```powershell
.\scripts\dev\check-hosted-env.ps1 -EnvFile ".env"
```

## Promotion Path

1. Deploy backend staging.
2. Confirm `/health` works.
3. Configure frontend public envs.
4. Deploy frontend preview/staging.
5. Run browser smoke against hosted URLs.
6. Promote only after hosted smoke passes.
