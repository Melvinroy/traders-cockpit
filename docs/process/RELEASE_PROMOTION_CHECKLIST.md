# Release Promotion Checklist

Use this checklist before opening or merging a promotion PR from `codex/integration-app` into `main`.

## Before the promotion PR

- all intended feature PRs into `codex/integration-app` are merged
- local worktree is clean before promotion work begins
- no unrelated local changes remain
- the branch is rebased or merged up to the latest remote integration state
- open follow-up risks are documented in the promotion PR
- promotion PR includes explicit known gaps, env/schema notes, QC evidence, and rollback steps

## Required validation

- backend CI passed on the current integration commit
- frontend CI passed on the current integration commit
- local backend `pytest -q` passed if backend changed
- local frontend `npm run lint`, `npm run test`, and `npm run build` passed if frontend changed
- browser QC evidence exists for visible UI changes
- the five cockpit baseline screenshots are refreshed for cockpit-state work
- production-facing UI work is promoted only after browser QC evidence is attached on the integration candidate
- if the target is a hosted environment, post-deploy smoke evidence exists or is explicitly scheduled as the first post-merge verification step

## Release review questions

- does this release follow the merge sequence `codex/* -> codex/integration-app -> main`
- does this promotion contain only staged, reviewed work
- are all schema or env changes reflected in docs
- are any live-trading controls still safely gated
- can this release be rolled back by reverting the promotion merge
- is there a hosted smoke plan with frontend URL, backend URL, env file, and artifact destination

## After merge to `main`

- confirm CI and deployment/host checks for the promoted revision
- confirm the merge commit is present on `main`
- update the linked `docs/issues/*.md` record to `Status: Closed`
- record the closing promotion commit in that issue doc
- delete merged feature branches now reachable from `main`
- prune stale local and remote tracking refs if needed
- tag the release if a versioned cut is needed
- document any operational follow-up in `docs/handoffs/` or the merged PR

## Post-Merge Verification

- verify the promoted `main` commit is the same commit reviewed in the promotion PR
- rerun the post-merge smoke or hosted-health checks required for the target environment
- for hosted targets, rerun `.\scripts\dev\run-hosted-smoke.ps1` and retain `hosted-smoke.health.json`, screenshot, console, and network artifacts
- confirm baseline artifacts and validation notes are still linked from the promotion PR
- record any first-24-hour monitoring follow-up in `docs/handoffs/`
