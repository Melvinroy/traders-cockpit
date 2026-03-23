# Support Runbook

Use this when a deployed cockpit is reachable but a core operator flow is failing. The first step for every case is to capture the current hosted smoke artifacts before changing anything.

## Blank page

Symptoms:

- frontend loads a white or nearly empty page
- browser console shows chunk or runtime failures
- `/health/ready` is healthy but the UI shell does not render correctly

Checks:

1. Open the browser console and review the latest `<label>.console.txt` artifact.
2. Confirm the frontend build matches the promoted commit.
3. Confirm `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_WS_URL` are set to the deployed backend.
4. Check the latest network artifact for failing `/_next/` assets or `500` frontend document requests.

Likely causes:

- stale or partial frontend deploy
- broken Next build artifact
- wrong public backend or websocket URL

Recovery:

1. Redeploy the frontend from the promoted commit.
2. Re-run hosted smoke.
3. If the failure persists, revert the promotion merge and redeploy the last known-good frontend build.

## Setup not loading

Symptoms:

- login works
- cockpit shell renders
- entering a ticker leaves setup panels empty or stuck in an idle state

Checks:

1. Confirm `hosted-smoke.health.json` reports `ready` and `deps` as `ok`.
2. Inspect `<label>.network.txt` for failing setup, market, or websocket requests.
3. Confirm backend `CORS_ORIGINS` includes the deployed frontend origin.
4. Confirm provider credentials and broker mode are present in the hosted env.

Likely causes:

- backend readiness is degraded
- CORS mismatch
- broker/quote provider outage or missing credentials
- websocket endpoint mismatch

Recovery:

1. Fix env drift first, especially CORS and public URL settings.
2. Re-run hosted smoke after redeploying backend config.
3. If provider dependencies are unhealthy, keep the deploy in paper-safe mode and document the incident in the release handoff.

## Pending order not cancelable

Symptoms:

- recent orders show a cancel action
- cancel returns an error or the order remains pending
- browser QC previously passed, but live operator cancel is failing now

Checks:

1. Confirm backend health is still `ok`.
2. Inspect backend logs for broker cancel failures and request IDs.
3. Confirm the pending order still exists in the broker-backed order source.
4. Review the latest browser network artifact for the cancel request status code.

Likely causes:

- broker-side order already changed state
- stale local order reconciliation
- runtime/backend deploy drift between frontend and backend revisions

Recovery:

1. Refresh recent orders from broker truth before retrying.
2. If broker truth shows the order is already closed, let reconciliation clear it.
3. If broker truth still shows pending, retry cancel once with the same request ID trail captured in logs.
4. If reconciliation is broken, revert to the last known-good backend deploy.

## Broker quote unavailable

Symptoms:

- setup loads partially but quote-driven values are missing or stale
- fallback copy appears repeatedly
- setup or preview actions degrade around quote-dependent math

Checks:

1. Inspect `/health/deps` for broker/provider dependency status.
2. Confirm market-data credentials are present and valid.
3. Review backend logs for broker quote lookup failures or fallback events.
4. Check whether the system is already using fallback technicals intentionally.

Likely causes:

- provider outage
- credential rotation drift
- rate limiting or network failure to the quote source

Recovery:

1. Restore credential/config health first.
2. If the provider is degraded, keep the app in paper-safe behavior and communicate that quotes are in fallback mode.
3. Re-run hosted smoke after the dependency returns to `ok`.

## Escalation rule

If any one of these flows fails and cannot be recovered by config correction or redeploy of the promoted commit, revert the promotion merge and record the incident in `docs/handoffs/`.
