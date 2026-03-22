> Status: Closed
> Branch: codex/feature-alpaca-offhours-runtime
> Opened: 2026-03-22
> Closed: 2026-03-22
> Closing Commit: 298c330

## Issue

The Docker-local personal-paper flow still handled off-hours setup and entry as if quotes must be live and market orders must either fill immediately or fail. That created raw `Failed to fetch` UI failures on weekends and did not match Alpaca's documented session and order rules.

## Why it matters

- off-hours setup should still work when Alpaca can provide a latest available bid/ask
- local paper trading should mirror Alpaca's actual order semantics, not a generic broker workflow
- queued and extended-hours orders must remain truthfully pending until the broker position exists
- position-management actions must stay blocked until the broker entry is filled

## Acceptance

- setup quote resolution prefers Alpaca latest quote, then snapshot quote, then most recent historical quote
- `GET /api/setup/{symbol}` includes:
  - `sessionState`
  - `quoteState`
- local personal-paper mode no longer surfaces raw browser `Failed to fetch` for setup failures
- off-hours entry requires an explicit choice:
  - `Queue For Open`
  - `Submit Extended-Hours Limit`
- queue-for-open uses standard Alpaca market order semantics and stays `entry_pending`
- extended-hours submission uses `limit` + `day` + `extended_hours=true`
- stop / profit / move-to-BE stay blocked while `entry_pending`
- flatten cancels the pending entry order instead of pretending a filled position exists
- Docker-local smoke validates the new setup metadata and off-hours entry request path
