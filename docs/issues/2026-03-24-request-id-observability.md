# Request ID and Structured Logging Foundation

> Status: Open
> Branch: `codex/feature-request-id-observability`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

The app has health checks and browser QC, but operational traces are still weak:

- API responses do not expose a stable request identifier for support/debugging
- server logs are not structured around request context
- auth, preview, enter, stop, profit, flatten, and cancel actions do not emit a consistent machine-readable log shape
- broker/runtime failures are harder to correlate across frontend, API, and backend logs than they should be

That makes production triage slower than necessary, especially for intermittent failures and user-reported issues.

## Business value

- support can ask for a request id and trace a failure quickly
- staging/production logs become much easier to search and group
- auth and trade actions get an auditable operational trail without relying on ad hoc prints
- this lays the groundwork for later correlation IDs across broker submissions and UI support runbooks

## Scope

- add request-id middleware for HTTP requests
- return a stable request-id header on API responses
- emit structured logs for auth and core trade/order actions
- include request id, method, path, status, latency, and key domain fields where appropriate
- keep the visible cockpit UI unchanged

## Acceptance criteria

- [x] every HTTP response includes a request-id header
- [x] request ids are reused from inbound headers when provided, otherwise generated server-side
- [x] request completion logs include request id, method, path, status, and duration
- [x] auth login/logout failures and successes emit structured logs
- [x] preview, enter, stops, profit, flatten, and order-cancel emit structured logs with request id
- [x] backend tests cover request-id propagation and response headers
- [x] repo docs capture the logging contract and troubleshooting usage

## Risks / constraints

- do not change the current cockpit layout or frontend behavior beyond optional response-header consumption
- avoid logging secrets, session tokens, or raw credentials
- keep the log shape simple JSON-like key/value output that works with default container/platform logs

## Validation

- `python -m ruff check backend/app`
- `python -m black --check backend/app backend/alembic/versions`
- `python -m pytest -q backend/app/tests/test_api.py`

## Notes

- Browser QC was intentionally skipped because this tranche does not change visible UI behavior.
