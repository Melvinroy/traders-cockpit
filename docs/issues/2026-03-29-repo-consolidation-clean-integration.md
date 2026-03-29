# Repo Consolidation to Clean Integration Baseline

> Status: Closed
> Branch: `codex/refactor-repo-clean-integration`
> Opened: 2026-03-29
> Closed: 2026-03-29
> Closing Commit: `86d6435`

## Problem

The repo currently has a clean `codex/integration-app` worktree, a separate broker-truth feature branch, and a dirty active checkout with additional unstaged frontend/script work. That makes it unclear which checkout is the real baseline for future work and promotion.

## Frozen Baseline

- active dirty checkout branch: `codex/feature-broker-truth-paper-promotion`
- active dirty checkout HEAD: `694d323beed234c130ebe3b5d3efcf11bde89127`
- local `codex/integration-app` HEAD: `ab0144aeb03edb773d7514a42854eef82f703625`
- remote `origin/codex/integration-app` HEAD: `ab0144aeb03edb773d7514a42854eef82f703625`
- local `main` HEAD: `5d16b8c6582ad1213e867bbb21d0c52b7af5ce9b`
- remote `origin/main` HEAD: `05ac6258838ec53fc77a6ef302028d0d9aa5c227`
- local `codex/feature-broker-truth-paper-promotion` HEAD: `694d323beed234c130ebe3b5d3efcf11bde89127`
- remote `origin/codex/feature-broker-truth-paper-promotion` HEAD: `694d323beed234c130ebe3b5d3efcf11bde89127`
- feature branch divergence vs integration: `47` commits on feature side, `5` commits on integration side
- worktrees present at freeze time: `30`

## Goals

- make one clean `codex/integration-app` checkout the only baseline
- quarantine dirty unstaged work so it is not implicitly promoted
- reconcile reviewed broker-truth work onto the current integration codebase
- close March 28 issue docs only after integration really contains the merged work
- prune only merged or clearly superseded local branches/worktrees

## Acceptance Criteria

- [x] parent cleanup handoff exists for the quarantined dirty checkout
- [x] broker-truth work is reconciled onto current integration and validated there
- [x] `codex/integration-app` is clean after merge
- [x] March 28 issue docs are updated to `Closed` with actual integration references
- [x] safe merged branches/worktrees are pruned where they are not active quarantine sources
- [x] no dirty checkout is treated as the repo baseline
