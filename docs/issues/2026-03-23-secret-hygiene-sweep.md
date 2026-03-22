# Secret Hygiene Sweep

> Status: In Progress
> Branch: `codex/bugfix-secret-hygiene`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

Committed example configuration and runtime defaults still include hard-coded login credentials that read like usable passwords.

## Business value

- reduce the chance that public repo readers treat sample credentials as real
- keep local setup and QC flows aligned with explicit non-secret placeholders
- make repo hygiene clearer before staged promotion

## Scope

- sanitize committed auth password defaults in examples, runtime config, and local QC scripts
- update tests to match the sanitized placeholders
- leave ignored local `.env` files untouched

## Acceptance criteria

- [ ] tracked config no longer publishes hard-coded auth passwords
- [ ] test and QC defaults use the sanitized placeholder values
- [ ] ignored local env files remain local-only

## Risks / constraints

- local users who relied on the old sample passwords must refresh their env files
- database and localhost service credentials used only for local infrastructure are not in scope for this sweep
