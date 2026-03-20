# Issue: Backend Hardening And Release Package

## Goal

Close the remaining production-hardening and release-readiness gaps after the first working vertical slice.

## Scope

- normalize realtime event fanout through Redis-backed pub/sub
- harden trade lifecycle validation and duplicate-order guards
- tighten broker safety and live-mode gating
- enrich normalized market-data and account contracts
- improve blotter and log audit fidelity
- finish OSS/release docs for integration-to-main promotion

## Acceptance

- websocket events work in single-process and Redis-backed modes
- backend rejects unsafe live-mode and duplicate execution paths
- browser QC captures idle, setup, trade-entered, protected, and profit-flow states
- README and release docs are sufficient for a contributor to run, validate, and promote the repo
