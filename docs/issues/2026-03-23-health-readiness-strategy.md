# Health and Readiness Strategy

> Status: Open
> Branch: `codex/feature-health-readiness`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The backend currently exposes only a single `/health` endpoint that behaves like a shallow liveness check. That is not enough for production operations:

- deploy platforms need a true readiness signal
- operators need structured dependency status for Postgres, Redis, and auth storage
- docs still talk about health checks without distinguishing live vs ready behavior

## Business value

Production incidents are easier to prevent and triage when health checks are explicit. This tranche gives the app a proper health strategy:

- `/health/live` for process liveness
- `/health/ready` for deployment readiness
- `/health/deps` for structured dependency visibility

## Scope

- add structured health/readiness reporting in backend runtime code
- expose `/health/live`, `/health/ready`, and `/health/deps`
- keep `/health` as a compatibility alias
- update hosted docs and Render to use readiness as the deployment check
- add backend tests for healthy and unhealthy readiness behavior

## Acceptance criteria

- [ ] `/health/live` returns a simple liveness response
- [ ] `/health/ready` returns 200 only when the app is actually ready
- [ ] `/health/deps` exposes dependency details for operational debugging
- [ ] `render.yaml` uses the readiness endpoint as the service health check
- [ ] backend tests cover ready and not-ready paths

## Risks / constraints

- readiness checks must be safe and quick enough for deployment probes
- the old `/health` path must remain compatible while operators transition
