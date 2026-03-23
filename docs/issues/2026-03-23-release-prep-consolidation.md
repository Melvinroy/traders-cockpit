# Release prep consolidation

## Summary
Create a clean release-prep branch from codex/integration-app, consolidate the current local cockpit UI/runtime work into a promotable state, and validate against the release checklist.

## Scope
- audit uncommitted local cockpit changes across active worktrees
- pull the intended 3010 UI/runtime state into a clean branch
- fix critical runtime and production blockers discovered during validation
- run required backend/frontend validation
- run browser QC and refresh evidence where feasible

## Validation
- frontend lint, tests, build
- backend Ruff, Black check, pytest
- browser QC on the consolidated candidate
- state clearly what remains non-release-ready if anything still blocks promotion
