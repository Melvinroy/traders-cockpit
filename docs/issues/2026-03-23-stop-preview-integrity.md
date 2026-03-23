# Stop Preview Integrity

> Status: Open
> Branch: `codex/feature-stop-preview-integrity`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The cockpit still shows unstable or misleading stop-mode preview behavior before protection is applied:

- switching between `S1`, `S1·S2`, and `S1·S2·S3` can leave draft counts or preview text out of sync
- the pre-protection preview path does not always tighten share distribution cleanly
- QC can pass the end-to-end trade flow while still warning on the preview-only stop-mode path

That is a production-readiness gap because the user should be able to trust the protection preview before execution, not only the final protected state.

## Business value

- stop-mode selection should be deterministic before protection is entered
- preview counts should reflect the exact shares that will be sent if the user executes the selected mode
- the UI should not emit avoidable QC warnings on a core order-protection path

## Scope

- trace the existing stop-ladder preview path in the current cockpit UI
- make stop-mode share allocation deterministic before protection is applied
- align preview text, visible row counts, and execution payload generation
- add targeted automated coverage for stop-mode preview switching
- capture browser evidence proving the preview path is stable

## Acceptance criteria

- [x] selecting `S1`, `S1·S2`, or `S1·S2·S3` before protection updates the visible stop draft consistently
- [x] preview rows and share totals match the payload that would be executed
- [x] switching between stop modes does not leave stale row state behind
- [x] automated coverage catches the previously unstable preview path
- [x] browser QC shows a clean stop-mode preview flow without warnings

## Risks / constraints

- this is cockpit-state behavior, so browser QC evidence is required
- the fix must preserve the current `3010` layout and stop panel structure
- this tranche should focus on preview integrity and not mix in unrelated profit-panel or layout changes

## Validation

### Frontend

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`

### Browser QC

- `node ../scripts/dev/browser-smoke.mjs` from `frontend/` with:
  - `FRONTEND_URL=http://127.0.0.1:3092`
  - `BACKEND_URL=http://127.0.0.1:8092`
  - `BROWSER_SMOKE_LABEL=dev-smoke-final`
- `node ../scripts/dev/browser-smoke.mjs` from `frontend/` with:
  - `FRONTEND_URL=http://127.0.0.1:3192`
  - `BACKEND_URL=http://127.0.0.1:8092`
  - `BROWSER_SMOKE_LABEL=prod-smoke`
- `node ../scripts/dev/fidelity-baselines.mjs` from `frontend/` with:
  - `FRONTEND_URL=http://127.0.0.1:3092`
  - `BACKEND_URL=http://127.0.0.1:8092`
- `node scripts/dev/trade-flow-qc.mjs` with:
  - `FRONTEND_URL=http://127.0.0.1:3092`
  - `BACKEND_URL=http://127.0.0.1:8092`

Artifacts:

- `frontend/output/playwright/dev-smoke-initial.png`
- `frontend/output/playwright/prod-smoke.png`
- `frontend/output/playwright/dev-smoke-final.png`
- `frontend/output/playwright/baseline-idle.png`
- `frontend/output/playwright/baseline-setup-loaded.png`
- `frontend/output/playwright/baseline-trade-entered.png`
- `frontend/output/playwright/baseline-protected.png`
- `frontend/output/playwright/baseline-profit-flow.png`
- `frontend/output/playwright/baseline-stop-mode-preview.png`
- `frontend/output/playwright/baseline-stop-mode-active.png`

## Notes

- the fix preserves a local per-trade stop preview draft until protective stop orders are actually committed
- browser QC is now strict for the pre-protection stop-mode preview path instead of allowing a warning to pass silently
