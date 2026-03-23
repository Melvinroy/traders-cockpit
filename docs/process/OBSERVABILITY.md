# Observability Contract

This app uses a simple request-scoped observability contract for API troubleshooting.

## Request IDs

- Every HTTP response includes the `X-Request-ID` header.
- If a request already includes `X-Request-ID`, the backend reuses it.
- If no request id is provided, the backend generates one server-side.
- Browser, API, proxy, and support tooling should preserve the same request id when possible.

## Structured backend logs

- Structured backend events are emitted through the `traders_cockpit` logger.
- Each event is a single JSON line.
- Common fields:
  - `ts`
  - `event`
  - `request_id`
  - `method`
  - `path`
  - `client_ip`
- HTTP completion events also include:
  - `status`
  - `duration_ms`

## Core event names

- `http.request.completed`
- `http.request.failed`
- `auth.me`
- `auth.me.unauthenticated`
- `auth.login.succeeded`
- `auth.login.failed`
- `auth.login.blocked`
- `auth.logout`
- `trade.preview`
- `trade.enter`
- `trade.stops`
- `trade.profit`
- `trade.flatten`
- `trade.move_to_be`
- `orders.cancel`

## Logging safety rules

- Do not log passwords, session cookies, or raw auth tokens.
- Do not log broker secrets or environment secrets.
- Prefer stable identifiers such as username, symbol, broker order id, and request id.

## Troubleshooting usage

1. Capture the `X-Request-ID` value from the failing browser/API response.
2. Search backend logs for that request id.
3. Correlate the request with the matching structured event:
   - auth issue -> `auth.*`
   - trade preview/entry/stops/profit/flatten -> `trade.*`
   - cancel issue -> `orders.cancel`
4. If the request never reached the app, check reverse-proxy or platform logs for the same request id if they propagate it.
