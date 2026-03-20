# Workflow

This repo follows a staged delivery flow modeled after `TradeCtrl`.

## Standard Flow

1. Create or link the issue.
2. Branch from `codex/integration-app`.
3. Implement on a scoped `codex/*` branch.
4. Validate locally.
5. Open a PR into `codex/integration-app`.
6. Validate integration.
7. Promote to `main` through a second PR.

## Current Branch Stages

- Stage 1: `codex/integration-app`
- Stage 2: `main`

## Validation Minimums

- frontend lint, typecheck, tests, and build when frontend changes
- backend Ruff, Black check, and pytest when backend changes
- visible UI changes should include browser QC evidence

## Durable Repo Memory

Use repo docs for durable context. Do not depend on chat history as the only source of truth.
