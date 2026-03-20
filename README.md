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

```powershell
.\scripts\dev\start-local.ps1
```

This starts:

- PostgreSQL on `55432`
- Redis on `56379`
- Backend on `8010`
- Frontend on `3010`

To stop the local stack:

```powershell
.\scripts\dev\stop-local.ps1
```

To run the full local QC path, including browser smoke:

```powershell
.\scripts\dev\run-qc.ps1 -StartStack
```

### Docker

```bash
docker compose up --build
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

- paper mode first
- live mode disabled unless explicitly allowed
- local session auth enabled by default
- broker and market-data adapters can fall back to deterministic local data for development and tests
- PostgreSQL on `55432` and Redis on `56379` are the default local persistence endpoints
- SQLite is fallback-only and should be enabled explicitly when needed

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

For release preparation, use:

- [`docs/process/STAGING_RELEASE_PLAYBOOK.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/STAGING_RELEASE_PLAYBOOK.md)
- [`docs/handoffs/2026-03-21-integration-readiness.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/handoffs/2026-03-21-integration-readiness.md)

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
