# Pending Order Cancel QC

> Status: Open
> Branch: `codex/feature-pending-cancel-qc`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The cockpit previously had a real regression where pending orders could be canceled through the backend, but the browser flow failed or looked broken because the frontend/runtime path was not being exercised by automated QC.

Current browser smoke covers shell load and the standard trade flow, but it does not explicitly prove that:

- a deterministic pending entry order can be created
- the cancel action is visible and usable in `Recent Orders`
- canceling the pending order updates the row state correctly in the browser

## Business value

- locking the cancel path into QC prevents a repeat of a previously user-visible failure
- production readiness needs a deterministic browser-level cancel regression check, not just API confidence
- canceling a pending order is a core recovery action in paper and live trading workflows

## Scope

- add a deterministic browser QC path for pending-order cancel
- ensure the path uses a reliably pending order configuration instead of a likely-to-fill order
- verify browser-visible state transitions in `Recent Orders`
- add targeted backend coverage if the cancel path lacks current regression protection
- keep the existing cockpit layout intact

## Acceptance criteria

- [x] browser QC creates a pending order deterministically
- [x] the `Cancel` action is visible for that order in `Recent Orders`
- [x] invoking cancel changes the order state to `CANCELED` in the browser
- [x] automated coverage would fail if the cancel path regressed again
- [x] validation evidence is captured in the repo artifact path

## Risks / constraints

- this must use paper-mode-safe order construction only
- the path should avoid mutating unrelated existing positions
- the fix should stay scoped to cancel regression coverage and deterministic pending-order setup

## Validation

- Backend: `python -m ruff check backend\app`
- Backend: `python -m black --check backend\app backend\alembic\versions`
- Backend: `python -m pytest -q backend\app\tests\test_api.py`
- Frontend: `npm run lint`
- Frontend: `npm run typecheck`
- Frontend: `npm run test`
- Frontend: `npm run build`
- Browser QC: `powershell -ExecutionPolicy Bypass -File scripts\dev\run-qc.ps1 -FrontendPort 3098 -FrontendProdPort 3198 -BackendPort 8098 -PostgresPort 55498 -RedisPort 56408`

## Evidence

- Pending cancel artifact: `frontend/output/playwright/pending-cancel-flow.png`
- Baselines refreshed:
  - `frontend/output/playwright/baseline-idle.png`
  - `frontend/output/playwright/baseline-setup-loaded.png`
  - `frontend/output/playwright/baseline-trade-entered.png`
  - `frontend/output/playwright/baseline-protected.png`
  - `frontend/output/playwright/baseline-profit-flow.png`

## Notes

- The local paper broker now supports realistic pending entry orders for non-marketable simple limits and for advanced entry classes, with synthetic broker ids so browser cancel coverage exercises the same order-management path as the cockpit UI.
- `scripts/dev/run-qc.ps1` now includes the deterministic pending cancel browser flow.
- `scripts/dev\fidelity-baselines.mjs` was updated to use explicit ready-state waits instead of `networkidle`, which is not stable on the polling cockpit UI.
