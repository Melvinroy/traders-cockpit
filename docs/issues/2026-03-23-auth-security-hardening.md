# Auth Security and Secret Hygiene Hardening

> Status: Open
> Branch: `codex/bugfix-auth-security`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The staged runtime is closer to releasable, but two production-facing security gaps remain obvious:

- `/api/auth/login` has no brute-force protection
- CI does not scan tracked files for obvious secret leakage or unsafe non-placeholder credential samples

There is also no durable operator runbook for rotating previously exposed credentials.

## Business value

Production readiness is not just about booting cleanly. Login abuse and committed secrets are both preventable classes of failure. This tranche makes the app safer to expose by throttling repeated login failures, adding a tracked secret-hygiene check, and documenting rotation steps.

## Scope

- add basic server-side login throttling for repeated failed auth attempts
- cover login throttling with backend tests
- add a repo secret-hygiene scan that runs in CI
- add a documented secret rotation runbook under `docs/process/`

## Acceptance criteria

- [ ] repeated failed logins are rate limited server-side
- [ ] backend tests cover the login throttle path
- [ ] CI fails on obvious committed secrets or unsafe sample credentials
- [ ] a secret rotation runbook exists in repo docs

## Risks / constraints

- throttling must not block successful normal login flow
- secret scanning should target high-signal repo risks and avoid noisy false positives
- this tranche does not rotate third-party credentials itself; it documents and enforces the repo side
