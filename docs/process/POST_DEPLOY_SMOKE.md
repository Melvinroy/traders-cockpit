# Post-Deploy Smoke

Use this after a hosted staging or production deploy. The goal is to prove that the deployed backend is alive, ready, dependency-clean, and that the hosted cockpit still completes the baseline login and setup-load browser path.

## Command

```powershell
.\scripts\dev\run-hosted-smoke.ps1 `
  -FrontendUrl "https://app.example.com" `
  -BackendUrl "https://api.example.com" `
  -EnvFile ".env.production.local"
```

For local validation of the wrapper against a disposable local stack, you may override the auth credentials explicitly:

```powershell
.\scripts\dev\run-hosted-smoke.ps1 `
  -FrontendUrl "http://127.0.0.1:3092" `
  -BackendUrl "http://127.0.0.1:8092" `
  -EnvFile ".env.production.example" `
  -AuthUsername "admin" `
  -AuthPassword "change-me-admin"
```

## What it checks

1. Validates the hosted env file with `check-hosted-env.ps1`.
2. Calls backend health endpoints:
   - `/health/live`
   - `/health/ready`
   - `/health/deps`
3. Fails immediately if any health endpoint is non-200 or reports `status != ok`.
4. Runs the hosted browser smoke against the provided frontend/backend URLs.

## Required evidence

The smoke is not complete unless all of these artifacts exist in `frontend/output/playwright/`:

- `<label>.health.json`
- `<label>.png`
- `<label>.console.txt`
- `<label>.network.txt`

The default label is `hosted-smoke`, so the default artifact set is:

- `frontend/output/playwright/hosted-smoke.health.json`
- `frontend/output/playwright/hosted-smoke.png`
- `frontend/output/playwright/hosted-smoke.console.txt`
- `frontend/output/playwright/hosted-smoke.network.txt`

## Promotion use

- Required for hosted staging before opening a production promotion PR.
- Required again after production deploy as post-merge verification evidence.
- Link the resulting artifact set from the promotion PR or the release handoff.
