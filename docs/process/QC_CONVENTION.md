# QC Convention

## Minimum Expectations

- frontend: lint, test, build
- backend: Ruff, Black check, pytest
- visible UI work: browser or screenshot evidence when practical
- cockpit state changes: maintain the baseline screenshot set for idle, setup-loaded, trade-entered, protected, and profit-flow states

## CI Evidence

- GitHub Actions uploads browser evidence as the `browser-qc-artifacts` artifact on CI runs
- the artifact should contain Playwright screenshots plus frontend/backend logs from `frontend/output/playwright/`

## If Something Is Skipped

State what was skipped and why.
