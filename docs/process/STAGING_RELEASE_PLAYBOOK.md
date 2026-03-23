# Staging Release Playbook

Use this when `codex/integration-app` is being prepared for promotion into `main`.

## Preconditions

- feature work merged into `codex/integration-app`
- open regressions or intentional deferrals documented in the promotion PR
- env and schema changes reflected in `.env.example`, README, and migration docs
- backup or snapshot plan prepared for any schema-affecting release

## Required Commands

```powershell
.\scripts\dev\run-qc.ps1 -StartStack
```

If Docker-based verification is needed:

```powershell
docker compose up --build
```

If schema-affecting files changed, confirm the dedicated migration-smoke CI job is green before opening the promotion PR.

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
- production-facing UI work must include browser QC evidence on the integration branch before promotion
- schema-affecting promotions must link the backup or snapshot reference in the PR summary

## Merge Sequence

1. Merge a dedicated `codex/*` branch into `codex/integration-app`.
2. Run staged validation on `codex/integration-app`.
3. Refresh required browser artifacts for any visible cockpit changes.
4. Open the promotion PR from `codex/integration-app` to `main`.
5. After merge to `main`, close linked issue docs and prune merged branches.

## PR Summary Template

State:

- what changed
- what was validated
- env/schema changes
- remaining known gaps
- rollback plan
- where screenshot/browser QC evidence is attached
