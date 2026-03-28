# Projection Rebuild Tooling

> Status: In Progress
> Branch: `codex/feature-hedge-hardening-foundation`
> Opened: 2026-03-28
> Closed: -
> Closing Commit: -

## Problem

Projection rows are disposable read models. The repo needs a recovery-friendly way to rebuild them after drift, operator cleanup, or database restore work without exposing that control in the public UI.

## Scope

- add a backend rebuild path for `position_projections`
- wrap it in a CLI-oriented recovery script for local and staging ops
- prove rebuild parity in automated tests

## Acceptance Criteria

- [ ] projections can be deleted and rebuilt from backend state
- [ ] the rebuild path is callable from a repo script
- [ ] a regression test proves rebuild parity for a fixture position
