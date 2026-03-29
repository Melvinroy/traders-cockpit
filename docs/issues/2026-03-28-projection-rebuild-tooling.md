# Projection Rebuild Tooling

> Status: Closed
> Branch: `codex/integration-app`
> Opened: 2026-03-28
> Closed: 2026-03-29
> Closing Commit: `86d6435`
> Review PR: [#33](https://github.com/Melvinroy/traders-cockpit/pull/33)
> Latest Commit: `86d6435`

## Problem

Projection rows are disposable read models. The repo needs a recovery-friendly way to rebuild them after drift, operator cleanup, or database restore work without exposing that control in the public UI.

## Scope

- add a backend rebuild path for `position_projections`
- wrap it in a CLI-oriented recovery script for local and staging ops
- prove rebuild parity in automated tests

## Acceptance Criteria

- [x] projections can be deleted and rebuilt from backend state
- [x] the rebuild path is callable from a repo script
- [x] a regression test proves rebuild parity for a fixture position
