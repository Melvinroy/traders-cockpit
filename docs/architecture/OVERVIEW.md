# Architecture Overview

## Monorepo Layout

- `frontend/`: Next.js cockpit UI that ports the supplied `UI.html` into a maintainable React app.
- `backend/`: FastAPI service for setup generation, trade lifecycle management, persistence, and realtime events.
- `scripts/`: local bootstrap, QC, migration, and release helpers.
- `docs/`: workflow, issue memory, architecture, and release handoffs.

## Runtime Model

### Frontend

- talks to the backend over REST for setup, account, positions, orders, and trade actions
- listens on `WS /ws/cockpit` for normalized `price_update`, `position_update`, `order_update`, and `log_update` events
- preserves the prototype's state-driven workflow: `idle -> setup_loaded -> entry_pending -> trade_entered -> protected -> P1_done -> P2_done -> runner_only -> closed`

### Backend

- computes setup data and risk sizing server-side
- persists positions, orders, and audit logs in PostgreSQL
- uses Redis-backed websocket fanout when Redis is available, while preserving single-process fallback for local simplicity
- keeps paper mode as the default execution path

## Data Contracts

### Setup

The setup payload is normalized around:

- midpoint-derived entry suggestion
- LoD-based default stop
- ATR/reference context
- computed risk sizing
- provider metadata and quote timestamp

### Orders

Orders are stored as a parent-child tree rooted on the entry order:

- root `MKT` entry order
- child `STOP` orders
- child `LMT` profit orders
- child `TRAIL` runner orders

### Activity Log

Every meaningful trade action appends a durable log row and is also eligible for realtime fanout to the UI.

## Safety Model

- live trading is disabled by default
- `alpaca_live` cannot become effective unless config explicitly allows it and a live confirmation token is present
- max notional, daily loss, and max-open-position checks are enforced server-side
- duplicate active stop and runner orders are rejected

## QC Model

The repo-owned QC path is:

1. backend tests
2. frontend lint, typecheck, tests, build
3. browser smoke against dev
4. browser smoke against prod preview
5. fidelity baselines and trade-flow screenshots

Artifacts land in `frontend/output/playwright/`.
