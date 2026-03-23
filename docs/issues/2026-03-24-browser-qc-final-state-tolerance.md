# Browser QC Final Stop-State Tolerance

> Status: Open
> Branch: `codex/bugfix-browser-qc-final-state`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

The integration branch browser QC is failing in `scripts/dev/trade-flow-qc.mjs` even though the trade flow itself completes.

The failing run ended with final stop statuses:

- `["FILLED", "CANCELED", "CANCELED"]`

That is a valid terminal paper-simulation outcome, but the QC script currently rejects it because the accepted final-state list is too narrow.

## Scope

- update the browser-QC trade-flow script to accept the additional valid terminal stop state
- keep the fix limited to QC tolerance, not runtime trading behavior
- rerun the real browser-QC harness locally against the patched branch

## Acceptance criteria

- [x] `scripts/dev/trade-flow-qc.mjs` accepts `["FILLED", "CANCELED", "CANCELED"]`
- [x] local browser-QC passes on the patched branch
- [ ] the fix is pushed in a dedicated `codex/bugfix-*` branch for merge into `codex/integration-app`

## Risks / constraints

- do not widen the accepted state set beyond what is justified by observed paper behavior
- do not change backend trade semantics in this tranche
- keep the change scoped so promotion can proceed once integration is green

## Validation

- `QC_FRONTEND_PORT=3142 QC_BACKEND_PORT=8142 python scripts/ci/run_browser_qc.py`
