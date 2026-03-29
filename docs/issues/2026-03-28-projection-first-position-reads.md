# Projection-First Position Reads

> Status: Closed
> Branch: `codex/integration-app`
> Opened: 2026-03-28
> Closed: 2026-03-29
> Closing Commit: `86d6435`
> Review PR: [#33](https://github.com/Melvinroy/traders-cockpit/pull/33)
> Latest Commit: `86d6435`

## Problem

The cockpit still has legacy mutable rows that can drift away from the operator-facing read state. Position reads need to come from the projection payload first so the UI renders broker-truthful, reconciliation-aware state.

## Scope

- serve `get_position` and `get_positions` from `position_projections.payload` first
- keep mutable state rows as build inputs and fallbacks only
- add rebuild tooling so deleted projections can be reproduced safely

## Acceptance Criteria

- [x] projection payload is the default served `PositionView`
- [x] changing a mutable row without syncing the projection does not change served state
- [x] deleting projection rows and rebuilding reproduces served position state for fixtures
