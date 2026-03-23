# Order Type/TIF/Class Guardrails

> Status: Open
> Branch: `codex/feature-order-type-tif-matrix`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The cockpit still allows users to assemble invalid or misleading entry combinations across:

- `Type`
- `TIF`
- `Class`
- session state
- extended-hours behavior

The backend eventually rejects many of these combinations, but the current `3010` UI mostly exposes them as plain selects and only blocks one special case (`OCO`). That leaves the user with a configuration that appears valid until preview or enter fails.

## Business value

Production readiness requires deterministic order-intent handling:

- selections should remain visible and stable
- invalid combinations should be blocked before order submission
- the user should see the specific reason a combination is invalid
- broker/session behavior should be explicit instead of inferred from failing API requests

## Scope

- add a broker/session-aware entry rule layer for `Type / TIF / Class`
- keep the existing cockpit layout and control placement intact
- surface invalid-combo reasons in the `Trade Entry` strip
- prevent preview/enter for invalid combinations without silently rewriting selections
- add backend and frontend coverage for the supported matrix

## Acceptance criteria

- [x] selecting `MARKET`, `LIMIT`, `STOP`, or `STOP LIMIT` never silently rewrites the chosen type
- [x] invalid `Type / TIF / Class` combinations remain selected but are blocked with clear copy
- [x] session-specific rules are surfaced in the UI before preview/enter
- [x] backend validation matches the UI guardrails for the implemented matrix
- [x] browser QC proves the entry strip behaves consistently on both dev and prod smoke paths

## Risks / constraints

- visible cockpit behavior changes require browser QC evidence
- this tranche must preserve the current `3010` layout and only tighten behavior
- the rule layer should stay broker-aware, but this tranche can still focus on the current Alpaca/paper execution path

## Validation

### Backend

- `python -m ruff check backend\app`
- `python -m black --check backend\app backend\alembic\versions`
- `python -m pytest -q backend\app\tests\test_api.py`

### Frontend

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`

### Browser QC

- `powershell -ExecutionPolicy Bypass -File scripts\dev\run-qc.ps1 -StartStack -FrontendPort 3086 -FrontendProdPort 3186 -BackendPort 8086 -PostgresPort 55486 -RedisPort 56396`

Artifacts:

- `frontend/output/playwright/dev-smoke-initial.png`
- `frontend/output/playwright/prod-smoke.png`
- `frontend/output/playwright/dev-smoke-final.png`
- `frontend/output/playwright/baseline-idle.png`
- `frontend/output/playwright/baseline-setup-loaded.png`
- `frontend/output/playwright/baseline-trade-entered.png`
- `frontend/output/playwright/baseline-protected.png`
- `frontend/output/playwright/baseline-profit-flow.png`

Notes:

- the rule guardrail layer now blocks invalid `Type / TIF / Class` combinations in the existing cockpit UI without rewriting the user’s selected values
- backend preview validation and frontend field-level copy are sourced from the same implemented matrix, so the browser and API paths now fail for the same reasons
