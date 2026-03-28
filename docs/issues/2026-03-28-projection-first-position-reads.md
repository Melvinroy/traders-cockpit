# Projection-First Position Reads

> Status: In Review
> Branch: `codex/feature-broker-truth-paper-promotion`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -
> Review PR: [#32](https://github.com/Melvinroy/traders-cockpit/pull/32)
> Latest Commit: `afb12ef`

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
