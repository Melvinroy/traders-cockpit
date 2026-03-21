# Decision: TradeCtrl Reuse Boundaries

## Status

Accepted

## Context

`TradeCtrl` already has mature patterns for env bootstrapping, auth/session handling, safety gates, and Alpaca integration structure. `traders-cockpit` should benefit from those conventions without inheriting `TradeCtrl`'s runtime state or database coupling.

## Decision

`traders-cockpit` will reuse and adapt `TradeCtrl` patterns in these areas:

- env/config naming and bootstrap conventions
- session-backed auth shape with opaque cookie tokens
- paper-first and live-gated broker safety defaults
- Alpaca adapter/controller structure where it improves maintainability

`traders-cockpit` will keep these areas fully separate:

- Postgres database and Alembic history
- auth/session store contents
- order, position, and audit-log data
- Redis/pubsub namespace
- frontend deployment envs and runtime state

## Consequences

- Both repos can share operator habits and env naming without risking state corruption.
- Hosted environments can be configured consistently across repos.
- Future Alpaca/auth hardening can be ported more easily from `TradeCtrl`.
- Data recovery and rollback remain isolated to `traders-cockpit`.
