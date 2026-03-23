# Broker Adapter Observability

> Status: Open
> Branch: `codex/feature-broker-adapter-observability`
> Opened: 2026-03-24
> Closed: -
> Closing Commit: -

## Problem

Request-scoped logging now exists at the API layer, but broker-facing and market-data adapter failures still disappear into generic errors too easily.

That leaves four operational blind spots:

- quote/setup fallback reasons are not structured in logs
- broker order submit failures are not emitted as structured events
- broker cancel failures and broker lookup fallbacks are not emitted as structured events
- retry-driven flows such as waiting for broker position fill are not easy to trace

## Scope

- add structured logs in broker adapters for submit, cancel, lookup, and retry/fallback paths
- add structured logs in market-data adapter for setup/quote fallback paths
- extend observability docs with broker and market-data event names
- add backend tests for broker fallback/retry log behavior

## Acceptance criteria

- [x] broker submit failures emit structured events
- [x] broker cancel failures and fallback/no-op paths emit structured events
- [x] market-data setup fallback emits structured events
- [x] broker wait/retry flow emits structured retry and success/failure events
- [x] backend tests cover fallback and retry log behavior
- [x] observability docs include the new event names

## Risks / constraints

- keep UI unchanged
- do not log secrets, raw credentials, or full auth cookies
- keep retry logging useful without becoming excessively noisy

## Validation

- `python -m ruff check backend/app`
- `python -m black --check backend/app backend/alembic/versions`
- `python -m pytest -q backend/app/tests/test_api.py`

## Notes

- Browser QC was intentionally skipped because this tranche has no visible UI change.
