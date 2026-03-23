# Hosted Auth Persistence

> Status: Open
> Branch: `codex/feature-hosted-auth-persistence`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

Hosted auth still depends on a separate SQLite file via `AUTH_DB_PATH`. That keeps staging and production tied to a mounted disk even though the app already requires Postgres and Redis for hosted environments.

Current issues:

- auth persistence is not aligned with the main database contract
- hosted readiness still has to validate a disk path for auth
- deployment docs and envs still carry a file-backed auth assumption

## Business value

Production auth should persist with the main database instead of a local file mount. That reduces deployment coupling and makes auth/session state align with the platform dependencies we already require.

This tranche will:

- add a database-backed auth store for hosted environments
- keep file-backed auth available for local development and tests
- move hosted env/docs away from `AUTH_DB_PATH` as a required production dependency

## Scope

- add config for auth storage mode selection
- implement a database-backed auth store using the primary database
- keep the existing file-backed auth store for local/test flows
- update startup preflight and readiness reporting for the new auth mode
- add the auth tables to Alembic migrations
- update env examples, hosted deployment docs, and Render config
- add backend tests for both auth storage modes

## Acceptance criteria

- [ ] hosted environments can use database-backed auth without `AUTH_DB_PATH`
- [ ] local development still works with file-backed auth
- [ ] auth startup/readiness checks reflect the selected auth storage mode
- [ ] Alembic creates the hosted auth tables safely
- [ ] backend tests cover both file-backed and database-backed auth resolution

## Risks / constraints

- auth data migration needs to avoid breaking existing local dev auth stores
- hosted auth should not silently fall back to file-backed storage
- the storage-mode split must stay explicit in docs and env contracts
