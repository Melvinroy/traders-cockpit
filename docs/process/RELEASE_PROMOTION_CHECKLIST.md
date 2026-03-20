# Release Promotion Checklist

Use this checklist before opening or merging a promotion PR from `codex/integration-app` into `main`.

## Before the promotion PR

- all intended feature PRs into `codex/integration-app` are merged
- no unrelated local changes remain
- the branch is rebased or merged up to the latest remote integration state
- open follow-up risks are documented in the promotion PR

## Required validation

- backend CI passed on the current integration commit
- frontend CI passed on the current integration commit
- local backend `pytest -q` passed if backend changed
- local frontend `npm run lint`, `npm run test`, and `npm run build` passed if frontend changed
- browser QC evidence exists for visible UI changes

## Release review questions

- does this promotion contain only staged, reviewed work
- are all schema or env changes reflected in docs
- are any live-trading controls still safely gated
- can this release be rolled back by reverting the promotion merge

## After merge to `main`

- confirm the merge commit is present on `main`
- tag the release if a versioned cut is needed
- document any operational follow-up in `docs/handoffs/` or the merged PR
