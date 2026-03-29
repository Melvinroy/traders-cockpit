# Hedge Hardening Foundation

> Status: In Review
> Branch: `codex/feature-broker-truth-paper-promotion`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -
> Review PR: [#32](https://github.com/Melvinroy/traders-cockpit/pull/32)
> Latest Commit: `afb12ef`

## Problem

The current cockpit still allows optimistic local state transitions that are not strictly tied to broker-confirmed fills and reconciled broker truth. That makes the stack usable for supervised simulation, but not for a safer solo-pro trading bar.

## Business value

- reduce false confidence in position, exit, and P&L state
- add durable event and reconciliation foundations for later hardening
- keep the current UI usable while the backend contract grows additively
- improve clean-checkout validation so the repo is easier to trust and promote

## Scope

- add append-only event and intent foundations in Postgres
- extend read models and API responses with reconciliation and blocking metadata
- remove optimistic live-broker exit handling where possible
- tighten auth/runtime guards and add CSRF protection for write actions
- fix frontend clean-checkout typecheck behavior

## Acceptance criteria

- [x] append-only trading event tables exist and are populated by core trade flows
- [x] entry/profit/flatten flows stop assuming broker-paper orders are instantly filled
- [x] setup payload can explicitly block execution when market data is stale or fallback-backed
- [x] write routes require session plus CSRF checks when auth is enabled
- [ ] frontend `npm run typecheck` passes from a clean checkout

## Risks / constraints

- the worktree already contains in-flight changes, so edits must preserve existing behavior where possible
- the current service layer is stateful and broad, so changes should be additive before deeper refactors
- browser QC is out of scope for this implementation slice
