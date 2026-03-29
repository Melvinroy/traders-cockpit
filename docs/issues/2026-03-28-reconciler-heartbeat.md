# Reconciler Heartbeat

> Status: Closed
> Branch: `codex/integration-app`
> Opened: 2026-03-28
> Closed: 2026-03-29
> Closing Commit: `86d6435`
> Review PR: [#33](https://github.com/Melvinroy/traders-cockpit/pull/33)
> Latest Commit: `86d6435`

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
