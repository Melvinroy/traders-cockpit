# Websocket and Correlation Observability

> Status: Open
> Branch: `codex/feature-websocket-observability`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

HTTP requests now have request IDs and the broker/market-data adapters emit structured events, but websocket traffic is still weakly correlated.

That leaves two real support gaps:

- websocket connect, disconnect, auth rejection, and publish flows are not consistently logged
- browser-triggered websocket events are harder to correlate with the originating request/session/user than normal HTTP flows

## Scope

- add websocket connection lifecycle logs
- add correlation identifiers for websocket sessions/messages
- include request/session/user context where available
- document the websocket observability contract
- add backend tests for websocket lifecycle logging where practical

## Acceptance criteria

- [x] websocket connect/disconnect/auth-failure events emit structured logs
- [x] websocket publish flow emits structured logs with a stable websocket/session correlation id
- [x] websocket events include enough context to correlate with user/session activity
- [x] observability docs include websocket event names and troubleshooting notes
- [x] backend validation passes for the tranche

## Risks / constraints

- keep visible UI unchanged
- do not log secrets, auth cookies, or full payloads unnecessarily
- keep websocket logging useful without flooding logs on every heartbeat/no-op

## Validation

- `python -m ruff check backend/app`
- `python -m black --check backend/app backend/alembic/versions`
- `python -m pytest -q backend/app/tests/test_api.py`
- `npm run lint`
- `npm run test`
- `npm run build`

## Notes

- Browser QC was intentionally skipped because this tranche does not change the visible cockpit UI.
