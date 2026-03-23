# Release Process Hardening

> Status: Open
> Branch: `codex/refactor-release-process-hardening`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The repository already has staging and promotion docs, but the release path still depends too much on convention and recent memory. Reviewers can miss screenshot evidence, env/schema drift, rollback detail, or the exact merge sequence because those requirements are spread across multiple files and not enforced consistently in the PR template.

## Business value

Production promotion should be boring. The repo needs one durable release-program record, one visible handoff board, and one consistent PR/checklist contract so staged work reaches `main` with the same evidence every time.

## Scope

- add a standing repo issue doc for the production-readiness program
- add a simple release board under `docs/handoffs/`
- tighten the PR template with screenshot, env/schema, known-gap, and rollback sections
- make the merge sequence explicit in process docs
- strengthen the release checklist with clean-worktree and post-merge verification requirements
- restate that production-facing work must land through `codex/integration-app` with browser QC evidence

## Acceptance criteria

- [ ] release-program issue doc exists and links to the release board
- [ ] release board exists under `docs/handoffs/`
- [ ] PR template requires screenshot evidence, env/schema notes, known gaps, and rollback
- [ ] release checklist includes clean-worktree and post-merge verification guidance
- [ ] merge sequence is explicitly documented as feature -> `codex/integration-app` -> `main`
- [ ] process docs explicitly require browser QC evidence for production-facing UI work

## Risks / constraints

- avoid duplicating process guidance without clarifying the single source of truth
- keep the docs lightweight enough that they are used, not ignored
