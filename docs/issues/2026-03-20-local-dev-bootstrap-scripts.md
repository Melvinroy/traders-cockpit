> Status: Closed (legacy backfill)
> Branch: historical / pre-lifecycle-header
> Opened: 2026-03-20
> Closed: 2026-03-22
> Closing Commit: Legacy backfill during repo hygiene; historical promotion commit predates required lifecycle headers
# Local Dev Bootstrap Scripts

GitHub issue: #4

## Problem

Local startup is currently manual and error-prone. Frontend and backend ports can collide with unrelated local services, and there is no single repo command for quality checks.

## Business value

This gives contributors one reliable path to boot the stack and one reliable path to validate it before opening a PR.

## Scope

- add local start scripts for frontend, backend, Postgres, and Redis
- detect occupied ports early with clear operator guidance
- add a single QC entrypoint for backend, frontend, and browser smoke
- document the commands in README

## Acceptance criteria

- [ ] local stack starts with one documented script path
- [ ] local QC runs with one documented script path
- [ ] port conflicts are handled explicitly

