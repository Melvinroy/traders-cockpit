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
- `market_data.setup.fallback`
- `market_data.setup.failed`
- `broker.entry.submit`
- `broker.entry.submit.fallback`
- `broker.entry.submit.failed`
- `broker.trailing.submit`
- `broker.trailing.submit.fallback`
- `broker.trailing.submit.failed`
- `broker.position.wait.retry`
- `broker.position.wait.succeeded`
- `broker.position.wait.failed`
- `broker.position.wait.fallback`
- `broker.position.close`
- `broker.position.close.fallback`
- `broker.position.close.failed`
- `broker.order.cancel`
- `broker.order.cancel.fallback`
- `broker.order.cancel.failed`
- `broker.orders.recent.fallback`
- `broker.orders.recent.failed`
- `broker.order.lookup`
- `broker.order.lookup.fallback`
- `broker.order.lookup.failed`
- `broker.session.lookup.fallback`
- `broker.session.lookup.failed`
- `broker.account.lookup.fallback`
- `broker.account.lookup.failed`
- `ws.auth.failed`
- `ws.connect`
- `ws.message.received`
- `ws.broadcast`
- `ws.disconnect`
- `ws.send.failed`
- `ws.redis.publish.failed`

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
   - broker submission/lookup/cancel issue -> `broker.*`
   - setup quote or fallback issue -> `market_data.*`
   - websocket connect/subscribe/publish issue -> `ws.*`
4. If the request never reached the app, check reverse-proxy or platform logs for the same request id if they propagate it.

## Websocket correlation

- The cockpit websocket now sends a stable `client_session_id` on connect and on outbound subscription messages.
- Websocket subscription messages also send a per-message `requestId`.
- Server-side websocket logs and websocket-triggered broker/service logs inherit that `requestId` and `client_session_id` where applicable.
- Server-originated websocket event payloads may include `requestId` so browser-side support captures can be correlated back to backend logs.
