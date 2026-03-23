# Hosted Smoke Readiness

> Status: Open
> Branch: `codex/feature-hosted-smoke-readiness`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The repo now has stronger env validation and runtime preflight checks, but the hosted deployment path is still missing a single operator command that proves the deployed frontend and backend work together. The Render blueprint is also under-specified for production-like staging because it does not declare a health check or a persistent auth storage path.

## Business value

Hosted readiness should be operable, not theoretical. This tranche gives the repo a documented post-deploy smoke command, makes the Render blueprint safer to deploy, and codifies the current hosted tradeoffs in docs.

## Scope

- add a hosted smoke wrapper that reuses the existing browser smoke flow against arbitrary frontend/backend URLs
- document the hosted post-deploy smoke path
- harden `render.yaml` with an explicit health check and persistent auth disk contract
- document the persistent-disk tradeoff for the current hosted auth model

## Acceptance criteria

- [ ] `scripts/dev/run-hosted-smoke.ps1` exists and can drive browser smoke against provided hosted URLs
- [ ] hosted deployment docs include the smoke command and expected artifacts
- [ ] `render.yaml` declares a health check path
- [ ] `render.yaml` declares a persistent auth storage path for the current hosted auth model

## Risks / constraints

- the current hosted auth model still depends on file-backed auth storage; this tranche documents and stabilizes it but does not replace it with Postgres-backed auth
- attaching a persistent disk on Render trades off zero-downtime deploys and horizontal scaling for durable auth state
