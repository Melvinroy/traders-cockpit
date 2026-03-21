# Workflow

This repo follows a staged delivery flow modeled after `TradeCtrl`.

## Standard Flow

1. Create or link the issue.
2. Add or update the matching `docs/issues/*.md` record with a lifecycle header.
2. Branch from `codex/integration-app`.
3. Implement on a scoped `codex/*` branch.
4. Validate locally.
5. Open a PR into `codex/integration-app`.
6. Validate integration.
7. Promote to `main` through a second PR.
8. After the promotion commit lands on `main`, mark the issue doc `Closed` and record the closing commit.
9. Delete merged `codex/*` branches once their commits are reachable from `main`.

## Current Branch Stages

- Stage 1: `codex/integration-app`
- Stage 2: `main`

## Validation Minimums

- frontend lint, typecheck, tests, and build when frontend changes
- backend Ruff, Black check, and pytest when backend changes
- visible UI changes should include browser QC evidence

## Required PR Structure

- feature PRs target `codex/integration-app`
- promotion PRs target `main` and use `codex/integration-app` as the head branch
- every PR links a GitHub issue or an explicit repo issue record in `docs/issues/`
- PR descriptions must include scope, risks, and validation notes

## Issue And Branch Closure

- keep `main` and `codex/integration-app` permanently
- keep active unmerged `codex/*` branches while work is in progress
- delete merged remote and local `codex/*` branches after promotion to `main`
- every issue doc must start with a lifecycle header:
  - `Status`
  - `Branch`
  - `Opened`
  - `Closed`
  - `Closing Commit`
- if older issue docs predate the header format, backfill them explicitly instead of leaving them ambiguous
- use [`scripts/dev/repo-hygiene.ps1`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/scripts/dev/repo-hygiene.ps1) to audit merged branches and issue-doc status drift

## Canonical Process Docs

- [`docs/process/BRANCH_PROTECTION.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/BRANCH_PROTECTION.md)
- [`docs/process/RELEASE_PROMOTION_CHECKLIST.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/RELEASE_PROMOTION_CHECKLIST.md)
- [`docs/process/QC_CONVENTION.md`](/Users/melvi/OneDrive/Desktop/Traders%20Cockpit/docs/process/QC_CONVENTION.md)

## Durable Repo Memory

Use repo docs for durable context. Do not depend on chat history as the only source of truth.
