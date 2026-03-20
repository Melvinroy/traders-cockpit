# Branch And PR Discipline Hardening

GitHub issue: #2

## Problem

The repo has a staged branch model, but the documented rules are still too light for repeatable contributor use. Branch protection expectations, required checks, and promotion criteria need to be explicit.

## Business value

This removes ambiguity from feature delivery, keeps `codex/integration-app` meaningful as staging, and preserves recoverable history before promotions to `main`.

## Scope

- document branch protection settings for GitHub
- document required CI checks by change type
- add a promotion checklist for `codex/integration-app` to `main`
- point README and AGENTS.md at the canonical process docs

## Acceptance criteria

- [ ] a contributor can follow docs alone to open the correct PR
- [ ] required checks are documented for frontend, backend, and browser QC
- [ ] promotion criteria into `main` are explicit
