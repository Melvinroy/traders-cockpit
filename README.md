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
- [`docs/process/BRANCHING_AND_WORKTREES.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/BRANCHING_AND_WORKTREES.md)
- [`AGENTS.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/AGENTS.md)

## Local Setup

### Docker

```bash
docker compose up --build
```

Frontend:

- http://127.0.0.1:3000

Backend:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

### Manual Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

## Architecture Notes

- The frontend preserves the prototype layout and state shape as closely as possible.
- The backend computes sizing, stop ladders, tranche splits, and state transitions server-side.
- Orders use parent-child hierarchy rooted on the entry order.
- Live trading is scaffolded but disabled by default.

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

## OSS

- License: MIT
- Contributions are welcome through issue-first, PR-first workflow

## Roadmap

- Real Alpaca paper execution with broker reconciliation
- Polygon-backed technicals and short-interest enrichment
- Realtime Redis event fanout beyond single-process dev mode
- Position snapshotting and richer audit trails
- Expanded smoke and browser QC coverage
