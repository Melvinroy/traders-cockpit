# Quarantined Dirty Checkout Inventory

> Source Checkout: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit`
> Source Branch: `codex/feature-broker-truth-paper-promotion`
> Source Head: `694d323beed234c130ebe3b5d3efcf11bde89127`
> Captured: 2026-03-29
> Parent Issue: [`2026-03-29-repo-consolidation-clean-integration.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit-clean-integration/docs/issues/2026-03-29-repo-consolidation-clean-integration.md)

## Disposition Rules

- `promote now`: move into the current integration cleanup branch
- `quarantine`: preserve as separate in-flight work and do not promote now
- `already superseded`: safe to ignore once the integrated replacement lands
- `drop after confirmation`: do not promote; remove only after a separate explicit cleanup pass

## Frontend

Disposition: `quarantine`

- `frontend/app/globals.css`
- `frontend/components/ActivityLog.tsx`
- `frontend/components/Cockpit.tsx`
- `frontend/components/CockpitHeader.tsx`
- `frontend/components/EntryPanel.tsx`
- `frontend/components/OpenPositionsList.tsx`
- `frontend/components/OrdersBlotter.tsx`
- `frontend/components/ProfitTakingPanel.tsx`
- `frontend/components/SetupPanel.tsx`
- `frontend/components/StopProtectionPanel.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/cockpit-ui.ts`
- `frontend/lib/types.ts`
- `frontend/next.config.mjs`
- `frontend/package.json`
- `frontend/tests/setup.ts`
- `frontend/components/OpenPositionsPanel.tsx`
- `frontend/components/RecentOrdersPanel.tsx`
- `frontend/components/RunningPnlPanel.tsx`
- `frontend/tsconfig.typecheck.json`
- `frontend/cockpit-ui-qc.png`

## Scripts and Local Runtime Tooling

Disposition: `quarantine`

- `scripts/dev/browser-smoke.mjs`
- `scripts/dev/common.ps1`
- `scripts/dev/docker-local-paper-smoke.mjs`
- `scripts/dev/fidelity-baselines.mjs`
- `scripts/dev/run-docker-local-paper-smoke.ps1`
- `scripts/dev/run-hybrid-local-paper-smoke.ps1`
- `scripts/dev/run-qc.ps1`
- `scripts/dev/start-local.ps1`
- `scripts/dev/trade-flow-qc.mjs`
- `scripts/dev/reset_local_cockpit_state.py`

## Docs and Notes

Disposition: `quarantine`

- `docs/issues/2026-03-23-secret-hygiene-sweep.md`
- `docs/issues/2026-03-23-setup-qc-timeout.md`
- `docs/issues/2026-03-23-trade-entry-order-config.md`
- `docs/issues/2026-03-24-sanity-qc-alpaca-paper.md`

## Miscellaneous

- `docker-compose.yml` — `quarantine`
- `Traders_Cockpit_System_Design_Learning_Series.docx` — `drop after confirmation`

## Next Handling Rule

None of the files in this handoff are part of the clean integration baseline until they are reintroduced through a separate scoped branch and reviewed PR.
