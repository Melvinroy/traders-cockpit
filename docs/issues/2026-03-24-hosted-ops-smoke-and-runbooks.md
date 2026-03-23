# Hosted Post-Deploy Smoke and Support Runbooks

> Status: Open
> Branch: `codex/feature-hosted-ops-smoke`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

The repo now has local QC, CI browser QC, and a hosted smoke wrapper, but the hosted operational path is still incomplete:

- there is no single post-deploy smoke command that validates health endpoints and browser entry flow against a hosted stack
- the release checklist does not explicitly require hosted smoke evidence after deploy
- support guidance for recurring operational failures is scattered and incomplete

That leaves production follow-through weak even after CI is green.

## Scope

- add a post-deploy smoke runner for hosted frontend/backend URLs
- document the post-deploy smoke flow and expected evidence
- add a support runbook for the known operational failures:
  - blank page
  - setup not loading
  - pending order not cancelable
  - broker quote unavailable
- wire the new hosted smoke evidence into the release/promotion docs

## Acceptance criteria

- [x] hosted smoke can be executed from one documented command
- [x] hosted smoke checks backend health before browser flow
- [x] hosted smoke produces browser artifacts in the standard Playwright output path
- [x] release docs explicitly require hosted smoke evidence after deploy
- [x] support runbook exists for the recurring operational failure cases

## Risks / constraints

- keep the change scoped to deployment/ops readiness
- do not reshape the cockpit UI
- keep hosted smoke compatible with the existing browser smoke/auth flow

## Validation

- `python scripts/dev/check-secret-hygiene.py`
- `powershell -ExecutionPolicy Bypass -File scripts/dev/start-local.ps1 -FrontendPort 3122 -FrontendProdPort 3222 -BackendPort 8122 -PostgresPort 55522 -RedisPort 56422`
- `powershell -ExecutionPolicy Bypass -File scripts/dev/run-hosted-smoke.ps1 -FrontendUrl http://127.0.0.1:3122 -BackendUrl http://127.0.0.1:8122 -EnvFile .env.production.example -AuthUsername admin -AuthPassword change-me-admin`
- `powershell -ExecutionPolicy Bypass -File scripts/dev/stop-local.ps1 -FrontendPort 3122 -BackendPort 8122 -PostgresPort 55522 -RedisPort 56422`
