# Retired Branch Worktrees During Final Branch Cleanup

> Captured: 2026-03-29
> Parent Issue: [2026-03-29-repo-consolidation-clean-integration.md](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit-health/docs/issues/2026-03-29-repo-consolidation-clean-integration.md)
> Cleanup Goal: keep only `main`, `codex/integration-app`, and `codex/quarantine-dirty-root-checkout`

## Purpose

This note records the non-baseline worktrees that were retired during the final branch cleanup.
Several of them still contained local-only edits or untracked issue notes. Those changes were not
promoted into the clean integration baseline and were intentionally removed to reach a single
maintainable repo state.

## Retired Worktrees With Local-Only Changes

- `codex/feature-order-rules-3010-merged`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-3010-integrated`
  Notes: local backend/frontend order-rules edits plus untracked `order_rules.py`, panel components, and issue note.

- `codex/feature-order-rules-3010-ui-integration`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-3010-order-rules`
  Notes: local backend/frontend order-rules edits plus untracked `order_rules.py`, panel components, and issue note.

- `codex/feature-order-rules-3010-repair`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-3010-repair`
  Notes: local backend/frontend order-rules edits plus untracked `order_rules.py`, panel components, and issue note.

- `codex/bugfix-pending-order-cancel`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-cancel-bug`
  Notes: local untracked issue note only.

- `codex/bugfix-integration-black-ci`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-integration-black-fix`
  Notes: local alembic edit plus untracked issue note.

- `codex/feature-main-promotion`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-main-promotion`
  Notes: local untracked promotion issue note only; branch was behind current integration.

- `codex/feature-broker-order-rules-engine`
  Path: `C:\Users\melvi\OneDrive\Desktop\Traders Cockpit-order-rules`
  Notes: local backend/frontend order-rules edits plus untracked `order_rules.py` and issue note.

## Retired Clean Or Superseded Worktrees

- `codex/feature-broker-adapter-observability`
- `codex/feature-pending-cancel-qc`
- `codex/feature-ci-browser-qc`
- `codex/feature-request-id-observability`
- `codex/feature-stop-preview-integrity`
- `codex/feature-order-type-tif-matrix`
- `codex/feature-websocket-observability`

## Result

After this cleanup, the repo keeps:

- `codex/integration-app` as the clean baseline
- `codex/quarantine-dirty-root-checkout` as the only preserved local quarantine branch
- `main` as the promotion target

All other local and remote branches are intentionally removed.
