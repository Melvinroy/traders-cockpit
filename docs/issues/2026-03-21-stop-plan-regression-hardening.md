> Status: Closed (legacy backfill)
> Branch: historical / pre-lifecycle-header
> Opened: 2026-03-21
> Closed: 2026-03-22
> Closing Commit: Legacy backfill during repo hygiene; historical promotion commit predates required lifecycle headers
# Stop Plan Regression Hardening

## Goal
Lock down stop-mode behavior so the cockpit consistently shows:

- `S1` as a single stop row
- `S1·S2` as two stop rows
- `S1·S2·S3` as three stop rows

This must hold both before stop execution and in later active states such as `PROTECTED` and `RUNNER ONLY`.

## Scope
- Add browser QC coverage for stop-mode row counts.
- Make stop-row statuses visually clearer in the UI.
- Preserve the existing backend stop-split behavior of `33 / 33 / 34` for blank `S1·S2·S3` percentages.

## Acceptance
- Browser QC fails if stop-mode selector counts regress.
- `S1`, `S2`, and `S3` remain understandable in later active states.
- Active, modified, canceled, and preview stop rows are visually distinguishable.

