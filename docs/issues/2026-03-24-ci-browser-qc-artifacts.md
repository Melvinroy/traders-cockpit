# CI Browser QC and Artifact Upload

> Status: Open
> Branch: `codex/feature-ci-browser-qc`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

The repo has local QC scripts and Playwright artifacts, but pull requests still rely on local evidence. CI does not currently execute the browser smoke path or upload screenshots/logs for review.

That leaves three gaps:

- PR reviewers cannot rely on durable browser evidence from CI
- promotion candidates can still pass backend/frontend checks without end-to-end browser proof
- screenshot/log artifacts are easy to lose because they are only local by default

## Scope

- add a CI browser QC job
- run the existing local-paper QC path in automation
- upload Playwright screenshots and relevant logs as GitHub Actions artifacts
- keep the visible UI unchanged

## Acceptance criteria

- [x] CI runs browser QC on pull requests and branch pushes
- [x] Playwright screenshots are uploaded as CI artifacts
- [x] QC logs are uploaded as CI artifacts
- [x] workflow fails if the browser QC script fails
- [x] repo docs mention where CI browser evidence lives

## Risks / constraints

- keep the change scoped to CI and QC tooling
- avoid introducing flaky CI by choosing a runner and script path that matches the existing QC harness
- preserve the current promotion flow through `codex/integration-app`

## Validation

- `python -m ruff check scripts/ci/run_browser_qc.py backend/app/services/cockpit.py backend/app/tests/test_api.py`
- `python -m black --check scripts/ci/run_browser_qc.py`
- `python -m black --check backend/app/services/cockpit.py`
- `python -m black --check backend/app/tests/test_api.py`
- `python -m pytest -q backend/app/tests/test_api.py`
- `npx playwright install chromium`
- `QC_FRONTEND_PORT=3131 QC_BACKEND_PORT=8131 python scripts/ci/run_browser_qc.py`

## Evidence

- local CI-style artifacts were generated under `frontend/output/playwright/`
- the GitHub Actions artifact name for this tranche is `browser-qc-artifacts`
