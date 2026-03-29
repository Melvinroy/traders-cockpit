# Broker Event Normalization

> Status: Closed
> Branch: `codex/integration-app`
> Opened: 2026-03-28
> Closed: 2026-03-29
> Closing Commit: `86d6435`
> Review PR: [#33](https://github.com/Melvinroy/traders-cockpit/pull/33)
> Latest Commit: `86d6435`

## Problem

Broker webhook payloads need a stable internal event contract so replay, dedupe, and downstream reconciliation can be deterministic. Raw broker payloads are too provider-shaped to be used directly as the service boundary.

## Scope

- normalize Alpaca webhook payloads into one internal event shape
- keep stable `event_id`, `fill_id`, `broker_order_id`, `symbol`, `event_type`, `occurred_at`, and `kind`
- dedupe external events before applying any local side effects
- preserve additive API behavior for the existing webhook route

## Acceptance Criteria

- [x] duplicate webhook deliveries do not create duplicate fills
- [x] duplicate webhook deliveries do not create duplicate event-log rows
- [x] duplicate webhook deliveries do not produce extra position transitions
- [x] malformed webhook payloads fail with a clear 400 response
