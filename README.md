# traders-cockpit

`traders-cockpit` is an open-source, production-style swing-trade management cockpit built from an existing HTML prototype and a backend contract. It uses a Next.js frontend, a FastAPI backend, PostgreSQL persistence, Redis-backed realtime fanout, and a staged GitHub workflow modeled after `TradeCtrl`.

## Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Alembic
- Data: PostgreSQL, Redis
- Realtime: WebSocket
- Tooling: Docker Compose, Ruff, Black, ESLint, Prettier, pytest, Vitest

## Repository Layout

- `frontend/` Next.js cockpit app
- `backend/` FastAPI service, DB models, migrations, tests
- `docs/` workflow docs, issue templates, durable repo memory
- `scripts/` development helpers and promotion scripts
- `.github/` GitHub Actions plus issue and PR templates

## Source Contracts

- [`UI.html`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/UI.html) is the visual and interaction contract
- [`Traders Cockpit.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/Traders%20Cockpit.md) is the backend and architecture contract
- `TradeCtrl` is the process and repo-hygiene reference
- [`docs/architecture/OVERVIEW.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/architecture/OVERVIEW.md) documents the current runtime architecture
- [`docs/architecture/COMPONENT_MATRIX.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/architecture/COMPONENT_MATRIX.md) tracks component status and TradeCtrl reuse boundaries

## Development Workflow

This repo uses a staged, recovery-friendly delivery flow.

1. Create or link an issue before implementation.
2. Branch from `codex/integration-app`.
3. Use `codex/feature-*`, `codex/bugfix-*`, or `codex/refactor-*`.
4. Open a PR into `codex/integration-app`.
5. Validate there first.
6. Promote with a PR from `codex/integration-app` into `main`.

See:

- [`docs/process/WORKFLOW.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/WORKFLOW.md)
- [`docs/process/BRANCH_PROTECTION.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/BRANCH_PROTECTION.md)
- [`docs/process/RELEASE_PROMOTION_CHECKLIST.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/RELEASE_PROMOTION_CHECKLIST.md)
- [`docs/process/BRANCHING_AND_WORKTREES.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/BRANCHING_AND_WORKTREES.md)
- [`AGENTS.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/AGENTS.md)

## Local Setup

### Recommended Local Bootstrap

For day-to-day prototyping, use the hybrid local path:

```powershell
Copy-Item .env.personal-paper.example .env.personal-paper.local
.\scripts\dev\start-hybrid-local-personal-paper.ps1
```

This starts:

- Frontend locally on `3010`
- Backend locally on `8010`
- PostgreSQL in Docker on `55432`
- Redis in Docker on `56379`

Why this is the default development path:

- much faster frontend/backend iteration
- real Alpaca paper quote and execution path
- same local Postgres/Redis persistence model
- no full Docker image rebuild on each code change

Use the full Docker-local path as the slower validation/signoff runtime:

```powershell
Copy-Item .env.personal-paper.example .env.personal-paper.local
.\scripts\dev\start-docker-local-personal-paper.ps1 -Build
```

This starts:

- Frontend on `3000`
- Backend on `8000`
- PostgreSQL on `55432`
- Redis on `56379`

If those localhost ports are already used by another stack, override them explicitly:

```powershell
.\scripts\dev\start-docker-local-personal-paper.ps1 -Build -FrontendPort 3100 -BackendPort 8100 -PostgresPort 55452 -RedisPort 56399
```

The Docker-local personal-paper path fails fast unless:

- `BROKER_MODE=alpaca_paper`
- `ALLOW_LIVE_TRADING=false`
- `ALLOW_CONTROLLER_MOCK=false`
- Alpaca paper credentials are present

For deterministic development and tests, keep using the existing script-driven local path:

```powershell
.\scripts\dev\start-local.ps1
```

To stop the Docker-local personal-paper stack:

```powershell
.\scripts\dev\stop-docker-local-personal-paper.ps1
```

To stop the hybrid local personal-paper stack:

```powershell
.\scripts\dev\stop-hybrid-local-personal-paper.ps1
```

To run the real Docker-local paper smoke flow:

```powershell
.\scripts\dev\run-docker-local-paper-smoke.ps1 -StartStack -Build
```

To run the fast hybrid-local paper smoke flow:

```powershell
.\scripts\dev\run-hybrid-local-paper-smoke.ps1 -StartStack
```

To validate and QC the script-driven personal-paper profile explicitly:

```powershell
.\scripts\dev\check-local-paper-readiness.ps1 -EnvFile ".env.personal-paper.local"
.\scripts\dev\run-qc.ps1 -StartStack -PersonalPaper -EnvFile ".env.personal-paper.local"
```

### Docker

```powershell
docker compose --env-file .env.personal-paper.local up --build -d
```

Frontend:

- http://127.0.0.1:3000

Backend:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

Infra host ports:

- PostgreSQL: `55432`
- Redis: `56379`

### Manual Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If you are not using `.\scripts\dev\start-local.ps1`, export `DATABASE_URL=postgresql://traders_cockpit:traders_cockpit@127.0.0.1:55432/traders_cockpit` and `REDIS_URL=redis://127.0.0.1:56379/0` before starting the backend.

To apply migrations against the repo-owned local Postgres runtime:

```powershell
.\scripts\dev\migrate-local.ps1
```

### Manual Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment

Copy `.env.example` to `.env` at the repo root and fill only the values you need. The backend boots env files from both the current working directory and the backend project directory, following the `TradeCtrl` pattern.

Important defaults:

- paper mode first for deterministic tests
- hybrid local personal-paper mode is the primary development runtime; Docker-local personal-paper is the validation/signoff runtime
- live mode disabled unless explicitly allowed
- local session auth enabled by default
- staged/hosted deployments should use `AUTH_COOKIE_SAMESITE=none` and `AUTH_COOKIE_SECURE=true` so the hosted frontend can authenticate against a separate backend origin
- auth sessions are stored separately from trading data in `AUTH_DB_PATH`, following the TradeCtrl session-store pattern without sharing the same database
- broker and market-data adapters can fall back to deterministic local data for development and tests
- in Docker-local personal-paper mode, the latest quote and execution path must come from Alpaca; derived technical fields remain fallback-backed for now
- if Alpaca quote or execution fails in Docker-local personal-paper mode, the app fails loudly instead of silently degrading to mock behavior
- PostgreSQL on `55432` and Redis on `56379` are the default local persistence endpoints
- SQLite is fallback-only and should be enabled explicitly when needed
- hosted Postgres URLs that begin with `postgresql://` are normalized by the backend to `postgresql+psycopg://` so Render-style connection strings work with the installed driver

Additional realtime/safety envs:

- `REDIS_CHANNEL_PREFIX` scopes websocket pub/sub fanout across environments
- `ALLOW_LIVE_TRADING=false` keeps live execution disabled even if `BROKER_MODE=alpaca_live`
- `LIVE_CONFIRMATION_TOKEN` must be present before live execution can become effective

## Architecture Notes

- The frontend preserves the prototype layout and state shape as closely as possible.
- The backend computes sizing, stop ladders, tranche splits, and state transitions server-side.
- Orders use parent-child hierarchy rooted on the entry order.
- Realtime fanout uses Redis when available and falls back to single-process websocket broadcast in local-only scenarios.
- Live trading is scaffolded but disabled by default.
- Setup responses now expose quote/technical/execution provider metadata so the UI can distinguish real Alpaca paper quotes from fallback-backed derived fields.
- TradeCtrl reuse is intentional for config/auth/safety patterns, while trading DB state stays isolated to `traders-cockpit`.

## Realtime Contract

`WS /ws/cockpit` publishes normalized envelopes:

- `price_update`
- `position_update`
- `order_update`
- `log_update`

The frontend still tolerates legacy local event names during the transition, but these normalized event names are now the intended contract.

## Testing

```bash
cd backend
pytest -q
```

```bash
cd frontend
npm run lint
npm run test
npm run build
```

Browser smoke and fidelity evidence are written under `frontend/output/playwright/` when using `.\scripts\dev\run-qc.ps1`.

Required state artifacts:

- `baseline-idle.png`
- `baseline-setup-loaded.png`
- `baseline-trade-entered.png`
- `baseline-protected.png`
- `baseline-profit-flow.png`

## Contribution

1. Create or link an issue.
2. Branch from `codex/integration-app`.
3. Open a PR back into `codex/integration-app`.
4. Run the repo QC path before asking for review.
5. Promote only through a separate PR from `codex/integration-app` into `main`.
6. After promotion, close the linked issue doc and delete merged feature branches.

For release preparation, use:

- [`docs/process/STAGING_RELEASE_PLAYBOOK.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/STAGING_RELEASE_PLAYBOOK.md)
- [`docs/handoffs/2026-03-21-integration-readiness.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/handoffs/2026-03-21-integration-readiness.md)

## Hosted Deployment

Recommended hosted topology:

- frontend on Vercel
- backend on Render or another Docker-capable host
- managed Postgres
- managed Redis

Deployment assets now included:

- [`frontend/Dockerfile`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/frontend/Dockerfile)
- [`backend/Dockerfile`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/backend/Dockerfile)
- [`render.yaml`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/render.yaml)
- [`docs/process/HOSTED_DEPLOYMENT.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/HOSTED_DEPLOYMENT.md)

Validate hosted envs before deploy:

```powershell
.\scripts\dev\check-hosted-env.ps1 -EnvFile ".env"
```

## OSS

- License: MIT
- Contributions are welcome through issue-first, PR-first workflow
- Protect `codex/integration-app` and `main` using [`docs/process/BRANCH_PROTECTION.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/BRANCH_PROTECTION.md)

## Roadmap

- Real Alpaca paper execution with broker reconciliation
- Polygon-backed technicals and short-interest enrichment
- Multi-instance Redis event fanout hardening in deployment environments
- Position snapshotting and richer audit trails
- Expanded smoke and browser QC coverage
