> Status: Closed (legacy backfill)
> Branch: historical / pre-lifecycle-header
> Opened: 2026-03-21
> Closed: 2026-03-22
> Closing Commit: Legacy backfill during repo hygiene; historical promotion commit predates required lifecycle headers
# Stop Coverage Hints

## Goal
Make each stop row explicitly show which tranches it covers so the stop plan is easier to audit in both preview and active states.

## Scope
- Add `T1 / T2 / T3` coverage hints to stop-plan rows.
- Use committed order coverage when stop orders exist.
- Use preview grouping when a stop plan is being configured before execution.

## Acceptance
- `S1` shows the tranches it protects.
- `S1·S2` shows grouped tranche coverage.
- `S1·S2·S3` shows one tranche per stop row.
- Coverage remains visible in protected and runner-only states.

