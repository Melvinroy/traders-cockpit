# AGENTS.md

This repo is built for long-term maintenance, staged promotion, and recovery-friendly delivery.

## Working Rules

- Start meaningful work with an issue.
- Use a dedicated `codex/*` branch for each coherent change.
- Target `codex/integration-app` before `main`.
- Keep changes scoped. Do not mix unrelated features.
- If UI changes are visible, capture validation evidence.
- If validation is skipped, state it explicitly.

## Branch Flow

1. Create or link the issue.
2. Branch from `codex/integration-app`.
3. Implement on `codex/feature-*`, `codex/bugfix-*`, or `codex/refactor-*`.
4. Open a PR into `codex/integration-app`.
5. Validate on integration.
6. Promote with a PR from `codex/integration-app` into `main`.

## Repo Memory

Chat is temporary. Durable knowledge belongs in the repo.

Use these folders when needed:

- `docs/issues/`
- `docs/decisions/`
- `docs/handoffs/`
- `docs/process/`

## Validation Minimums

- Frontend lint, tests, and build when frontend changes
- Backend Ruff, Black check, and pytest when backend changes
- Browser QC for visible UI work

## Safety Defaults

- Paper mode first
- Live mode disabled by default
- No secrets in source control
- Use `.env.example` as the public config contract
