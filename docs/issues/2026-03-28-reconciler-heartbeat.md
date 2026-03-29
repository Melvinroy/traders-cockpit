# Reconciler Heartbeat

> Status: In Review
> Branch: `codex/feature-broker-truth-paper-promotion`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -
> Review PR: [#32](https://github.com/Melvinroy/traders-cockpit/pull/32)
> Latest Commit: `afb12ef`

## Problem

The stack can reconcile on demand and from webhook ingress, but it does not yet maintain a durable freshness heartbeat. Without periodic poll-driven reconciliation, `broker_paper` execution can look healthy while local state is actually stale.

## Scope

- add a background reconcile loop with fast and slow cadence modes
- persist poll freshness in `reconcile_runs`
- expose reconcile freshness through setup and account payloads
- block trade-mutating actions when reconciliation is stale

## Acceptance Criteria

- [x] open working orders use the fast heartbeat cadence
- [x] idle periods use the slow heartbeat cadence
- [x] setup and account payloads surface reconcile freshness
- [x] stale reconciliation blocks trade-mutating routes with a stable reason string
