# Issue: Stop Local Cleanup Reliability

## Summary

`scripts/dev/stop-local.ps1` does not reliably terminate all locally started backend/frontend listeners. Repeated QC runs can leave orphaned Python listeners on the configured ports, which then blocks later `start-local` and `run-qc` executions.

## Scope

- Kill all listener-owning processes for the requested frontend/backend ports, not only the first match.
- Terminate the full process tree for listener processes started through `cmd.exe`.
- Wait for each port to stay closed before considering cleanup complete.

## Acceptance

- Repeated `start-local -> stop-local -> start-local` cycles do not leave stale listeners.
- `run-qc.ps1 -StartStack` can run twice in a row without manual port cleanup.
