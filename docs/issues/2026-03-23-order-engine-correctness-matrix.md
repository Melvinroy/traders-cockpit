# Order Engine Correctness Matrix

> Status: Open
> Branch: `codex/feature-order-engine-matrix`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The current order-entry and protection flow still has correctness gaps that block a real production claim:

- order intent is still effectively long-only in parts of the backend path
- `Type`, `TIF`, and `Class` do not map cleanly to the existing `3010` cockpit flow in every combination
- `SIMPLE` and class-driven attached exits can still leak state into each other
- the entry strip semantics and the stop/profit draft semantics are not decision-complete across the supported broker/session modes

## Business value

The production release can only be credible if entry behavior is deterministic and explainable across the supported matrix:

- `broker`
- `side`
- `type`
- `TIF`
- `class`
- `session`

This tranche is meant to harden the order engine so the existing cockpit UI maps to correct behavior instead of relying on partial defaults and ad hoc resets.

## Scope

- audit the current order-entry path in backend and frontend
- define and implement the supported order matrix for the existing cockpit UI
- fix long/short, type/TIF/class, and stop/profit draft interactions
- add backend and browser coverage for the supported matrix

## Acceptance criteria

- [x] `BUY` and `SELL` both map correctly end to end
- [ ] `MARKET`, `LIMIT`, `STOP`, and `STOP_LIMIT` do not silently rewrite to another type
- [ ] `SIMPLE` retains normal multi-leg stop/profit drafts until fill
- [ ] `BRACKET`, `OTO`, and compatibility `OCO` constrain the stop/profit panels correctly without leaking back into `SIMPLE`
- [ ] supported `type x TIF x class x broker x session` combinations are tested and blocked with explicit reasons when invalid

## Risks / constraints

- this tranche touches both backend lifecycle logic and visible cockpit behavior
- visible UI changes require browser QC and refreshed cockpit baselines
- the existing `3010` layout should stay intact while the underlying mapping is corrected

## Progress

- added explicit `side` to the shared order draft and backend schema
- made backend entry, stop, profit, trailing-stop, cancel, and P&L paths side-aware for long and short flows
- added `BUY / SELL` to the existing `3010` entry strip without changing the overall cockpit layout
- corrected frontend stop/target/runner math, open-position unrealized P&L, and active-stop display to respect side
- added backend coverage for sell-side preview validation and short exit-order routing
- hardened `scripts/dev/run-qc.ps1` so browser smoke uses the correct backend/prod ports and fails on native command errors

## Validation

- `python -m ruff check backend\app`
- `python -m black --check backend\app backend\alembic\versions`
- `python -m pytest -q backend\app\tests\test_api.py`
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `powershell -ExecutionPolicy Bypass -File scripts\dev\run-qc.ps1 -StartStack -FrontendPort 3078 -FrontendProdPort 3178 -BackendPort 8078 -PostgresPort 55478 -RedisPort 56388`

## Browser evidence

- `frontend/output/playwright/dev-smoke-initial.png`
- `frontend/output/playwright/prod-smoke.png`
- `frontend/output/playwright/dev-smoke-final.png`
- `frontend/output/playwright/baseline-idle.png`
- `frontend/output/playwright/baseline-setup-loaded.png`
- `frontend/output/playwright/baseline-trade-entered.png`
- `frontend/output/playwright/baseline-protected.png`
- `frontend/output/playwright/baseline-profit-flow.png`
