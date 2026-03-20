# Integration Readiness Handoff

## Branch

- source branch: `codex/feature-frontend-fidelity-recovery`
- target integration branch: `codex/integration-app`

## Included In This Tranche

- Redis-backed websocket fanout fallback path
- normalized realtime event envelopes
- stronger trade lifecycle guards
- live-mode gating hardening
- richer setup, account, and order audit payloads
- deeper browser QC with mandatory state screenshots
- additional frontend fidelity and audit polish

## Validation

- backend `python -m pytest -q`
- frontend `npm run lint`
- frontend `npm run typecheck`
- repo QC `.\scripts\dev\run-qc.ps1`

## Remaining Gaps

- final literal 1:1 cosmetic parity to every spacing/detail in `UI.html`
- broader provider-backed market-data enrichment beyond the normalized current contract
- external broker reconciliation beyond the current guarded paper-first path

## Promotion Guidance

- merge into `codex/integration-app`
- re-run `.\scripts\dev\run-qc.ps1 -StartStack` on integration
- open promotion PR to `main` only after the integration branch is green
