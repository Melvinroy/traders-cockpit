# Projection-First Position Reads

> Status: In Progress
> Branch: `codex/feature-hedge-hardening-foundation`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -

## Problem

The cockpit still has legacy mutable rows that can drift away from the operator-facing read state. Position reads need to come from the projection payload first so the UI renders broker-truthful, reconciliation-aware state.

## Scope

- serve `get_position` and `get_positions` from `position_projections.payload` first
- keep mutable state rows as build inputs and fallbacks only
- add rebuild tooling so deleted projections can be reproduced safely

## Acceptance Criteria

- [ ] projection payload is the default served `PositionView`
- [ ] changing a mutable row without syncing the projection does not change served state
- [ ] deleting projection rows and rebuilding reproduces served position state for fixtures
