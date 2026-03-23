# Env and Runtime Contract Hardening

> Status: Open
> Branch: `codex/refactor-env-parity-contract`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The repo's runtime contract is still split across `.env.example`, `docker-compose.yml`, README deployment guidance, and ad hoc startup scripts. That leaves real mismatches:

- local Docker defaults do not match the deterministic paper-first contract
- hosted validation is too weak to catch insecure or localhost-bound envs
- backend startup does not fail fast on broken Postgres/Redis/auth-path assumptions
- CI does not guard the config contract from drifting away from `.env.example` and README

## Business value

Production readiness depends on deterministic startup and a stable public config contract. This tranche makes the repo safer to promote by tightening env defaults, documenting a hosted profile, adding startup preflight checks, and failing CI when the runtime contract drifts.

## Scope

- add a documented `.env.production.example`
- align `docker-compose.yml`, README, and hosted deployment docs with the same runtime contract
- strengthen hosted env validation rules
- add backend startup preflight checks for Postgres, Redis, and auth DB path safety
- add a CI config-contract check against `.env.example`, `.env.production.example`, and README

## Acceptance criteria

- [ ] `.env.production.example` exists and is documented
- [ ] Docker defaults stay paper-first and align with repo docs
- [ ] hosted env validation fails on insecure or localhost-bound production config
- [ ] backend production/staging startup fails fast on broken DB/Redis/auth-path assumptions
- [ ] CI checks the config contract for drift against `.env.example` and README

## Risks / constraints

- startup hardening must not break deterministic local paper mode
- hosted validation should block unsafe production config without overfitting to one provider
- docs and config need to stay explicit without creating a second conflicting source of truth
