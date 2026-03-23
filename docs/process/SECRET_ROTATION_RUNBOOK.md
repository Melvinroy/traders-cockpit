# Secret Rotation Runbook

Use this runbook whenever credentials are suspected to be exposed in git history, screenshots, CI logs, or shared chat.

## Trigger Conditions

Rotate secrets immediately if any of these happen:

- a real API key or password is committed to a tracked file
- a credential is pasted into GitHub, chat, or a support ticket
- a deployment env dump or screenshot exposes a secret value
- a teammate reports a leaked or reused credential

## Immediate Containment

1. Disable the affected credential at the provider if possible.
2. Replace it with a newly generated credential.
3. Update the hosted env store first, then local private env files.
4. Confirm tracked repo files still contain placeholders only.
5. Run `python scripts/dev/check-secret-hygiene.py`.

## Provider Rotation Checklist

### Alpaca

1. Generate a new paper or live key in Alpaca.
2. Update the hosted env store and any private local env files:
   - `ALPACA_API_KEY_ID`
   - `ALPACA_API_SECRET_KEY`
3. Verify `ALLOW_LIVE_TRADING` is still `false` unless the live path is intentionally enabled.

### Polygon / Massive

1. Rotate the provider key.
2. Update:
   - `MASSIVE_API_KEY`
   - `POLYGON_API_KEY`
3. Re-run the hosted env check if those values are used in hosted environments.

### Ops / signing secrets

1. Rotate:
   - `OPS_API_KEY`
   - `OPS_ADMIN_API_KEY`
   - `OPS_SIGNING_SECRET`
2. Restart affected services after the env update.

### Seeded auth credentials

1. Change hosted admin and trader credentials.
2. Keep tracked env examples on `change-me-*` placeholders only.
3. If seeded hosted users are not required, keep `AUTH_SEED_USERS=false`.

## Repo Cleanup

1. Replace the tracked secret with a placeholder in the branch.
2. Open a dedicated `codex/bugfix-*` branch for the cleanup if one does not already exist.
3. Add an issue doc under `docs/issues/` describing the exposure and fix path.
4. If the secret reached `main`, use a follow-up PR and document the closing commit.
5. Do not rewrite protected branch history unless there is an explicit incident decision to do so.

## Validation

- `python scripts/dev/check-secret-hygiene.py`
- relevant backend/frontend validation if runtime config changed
- hosted env validation if public deployment config changed:

```powershell
.\scripts\dev\check-hosted-env.ps1 -EnvFile ".env.production.local"
```

## Follow-Up

- document the incident and rotation result in `docs/handoffs/`
- record whether any tokens were revoked, rotated, or confirmed unused
- prune stale branches containing the leaked value once the fix is merged
