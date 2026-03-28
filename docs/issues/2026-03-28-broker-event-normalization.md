# Broker Event Normalization

> Status: In Review
> Branch: `codex/feature-broker-truth-paper-promotion`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -
> Review PR: [#32](https://github.com/Melvinroy/traders-cockpit/pull/32)
> Latest Commit: `afb12ef`

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
