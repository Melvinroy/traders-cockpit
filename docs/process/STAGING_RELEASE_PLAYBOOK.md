# Staging Release Playbook

Use this when `codex/integration-app` is being prepared for promotion into `main`.

## Preconditions

- feature work merged into `codex/integration-app`
- open regressions or intentional deferrals documented in the promotion PR
- env and schema changes reflected in `.env.example`, README, and migration docs

## Required Commands

```powershell
.\scripts\dev\run-qc.ps1 -StartStack
```

If Docker-based verification is needed:

```powershell
docker compose up --build
```

## Required Browser Artifacts

The following files must exist after QC:

- `frontend/output/playwright/baseline-idle.png`
- `frontend/output/playwright/baseline-setup-loaded.png`
- `frontend/output/playwright/baseline-trade-entered.png`
- `frontend/output/playwright/baseline-protected.png`
- `frontend/output/playwright/baseline-profit-flow.png`

## Promotion Notes

- merge feature branches into `codex/integration-app` first
- validate on integration before opening the promotion PR
- promote only from `codex/integration-app` into `main`
- if rollback is needed, revert the promotion merge rather than rewriting history

## PR Summary Template

State:

- what changed
- what was validated
- env/schema changes
- remaining known gaps
- rollback plan
