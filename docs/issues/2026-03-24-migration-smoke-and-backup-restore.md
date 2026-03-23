# Migration Smoke and Backup/Restore Readiness

> Status: Open
> Branch: `codex/feature-migration-smoke`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

The repo now validates backend tests and browser QC in CI, but schema safety is still under-specified:

- CI does not run a dedicated Alembic migration smoke against a clean Postgres instance
- production promotion docs do not require a backup or snapshot plan before schema-affecting deploys
- operators do not have a single documented backup/restore reference

That leaves schema promotion weaker than the rest of the release path.

## Scope

- add a dedicated migration smoke runner
- add a CI job that runs Alembic upgrade smoke against clean Postgres
- document backup/restore expectations for production-style Postgres deploys
- require migration smoke and backup planning in the release docs

## Acceptance criteria

- [x] CI includes a migration smoke job
- [x] migration smoke verifies the current Alembic head and required tables after upgrade
- [x] a backup/restore runbook exists in `docs/process/`
- [x] release docs require backup/snapshot planning before schema-affecting promotions

## Risks / constraints

- keep the change scoped to schema safety and release operations
- do not change runtime application behavior
- keep the migration smoke deterministic on a clean Postgres instance

## Validation

- `python scripts/dev/check-secret-hygiene.py`
- `python -m ruff check scripts/ci/run_migration_smoke.py`
- `python -m black --check scripts/ci/run_migration_smoke.py`
- `POSTGRES_HOST_PORT=55524 docker compose up -d postgres`
- `DATABASE_URL=postgresql://traders_cockpit:change-me-postgres@127.0.0.1:55524/traders_cockpit python scripts/ci/run_migration_smoke.py`
- `POSTGRES_HOST_PORT=55524 docker compose stop postgres`
