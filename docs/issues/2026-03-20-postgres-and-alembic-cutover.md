# PostgreSQL And Alembic Migration Cutover

GitHub issue: #6

## Problem

PostgreSQL and Alembic exist in the repo, but config defaults and docs still leave SQLite looking like the normal local path instead of the narrow fallback path.

## Business value

This makes local and staging behavior match the intended production shape, reduces persistence drift between environments, and keeps migrations as the durable schema contract.

## Scope

- move default local config and docs to PostgreSQL + Redis
- keep SQLite only as an explicit fallback choice
- make Alembic the schema owner in local/staging workflows
- document the migration command path clearly

## Acceptance criteria

- [ ] root env example points to the repo-owned Postgres and Redis ports
- [ ] backend config defaults to PostgreSQL outside explicit fallback usage
- [ ] local bootstrap and docs use Alembic before app startup
