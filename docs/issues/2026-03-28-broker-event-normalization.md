# Broker Event Normalization

> Status: In Progress
> Branch: `codex/feature-hedge-hardening-foundation`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -

## Problem

Broker webhook payloads need a stable internal event contract so replay, dedupe, and downstream reconciliation can be deterministic. Raw broker payloads are too provider-shaped to be used directly as the service boundary.

## Scope

- normalize Alpaca webhook payloads into one internal event shape
- keep stable `event_id`, `fill_id`, `broker_order_id`, `symbol`, `event_type`, `occurred_at`, and `kind`
- dedupe external events before applying any local side effects
- preserve additive API behavior for the existing webhook route

## Acceptance Criteria

- [ ] duplicate webhook deliveries do not create duplicate fills
- [ ] duplicate webhook deliveries do not create duplicate event-log rows
- [ ] duplicate webhook deliveries do not produce extra position transitions
- [ ] malformed webhook payloads fail with a clear 400 response
