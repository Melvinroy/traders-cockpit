# Local-First Paper Trading and Repo Hygiene

> Status: In Progress
> Branch: `codex/feature-local-paper-and-repo-hygiene`
> Opened: 2026-03-22
> Closed: -
> Closing Commit: -

## Problem

Local development still defaults to a mock-friendly runtime, frontend errors expose raw backend `detail` payloads, and merged `codex/*` branches plus issue docs are not being cleaned up consistently after promotion.

## Business value

- make the local stack usable for real Alpaca paper trading instead of feeling like a demo
- show clearly which setup fields are real and which are fallback-backed
- keep the repository process trustworthy by closing stale branches and issue records promptly

## Scope

- add a dedicated local personal-paper profile and readiness check
- wire local startup and QC to support that profile explicitly
- expose provider provenance through the setup contract and frontend
- normalize frontend-facing API error messages and websocket reconnect behavior
- add issue/branch lifecycle rules, a cleanup script, and backfill the repo process expectations

## Acceptance criteria

- [x] local personal-paper mode starts with `BROKER_MODE=alpaca_paper` and validates paper credentials/readiness before boot
- [x] setup responses expose real-vs-fallback provider metadata
- [x] frontend no longer surfaces raw JSON `detail` blobs as runtime errors
- [x] websocket reconnects cleanly after local backend restarts
- [x] merged feature branches and missing issue-status docs can be audited and cleaned with repo tooling

## Risks / constraints

- derived setup fields remain fallback-backed in this tranche
- local personal-paper readiness should fail fast on missing Alpaca paper credentials rather than silently pretending to be live
- legacy issue docs predate lifecycle headers, so they need an explicit backfill policy rather than invented historical closure data
