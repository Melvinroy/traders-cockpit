# Integration Black Blocker

> Status: Proposed
> Branch: `codex/feature-integration-promote-release-prep`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

PR #10 into `codex/integration-app` is blocked by backend CI because `black --check .` wants to reformat `backend/alembic/versions/0001_initial.py`.

## Business value

Clearing this blocker is required before the validated cockpit candidate can merge into `codex/integration-app` and continue through the staged promotion path to `main`.

## Scope

- reformat the Alembic migration file without changing migration behavior
- re-run the integration candidate validation
- update the open integration PR with the fix

## Acceptance criteria

- [ ] `backend/alembic/versions/0001_initial.py` passes Black unchanged semantically
- [ ] GitHub backend CI is green on PR #10
- [ ] the integration PR is no longer blocked by the migration formatting issue

## Risks / constraints

- do not change migration semantics while reformatting
- do not mix unrelated behavior changes into this blocker fix
