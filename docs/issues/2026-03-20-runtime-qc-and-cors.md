# Runtime QC And CORS Stabilization

## Problem

The local cockpit rendered, but browser verification exposed two operational defects:

- frontend browser requests could fail against the backend because credentialed CORS was too permissive to be valid
- backend stop-order creation could generate duplicate `order_id` values inside the same transaction

## Business value

This work turns the scaffold into a verifiable local development slice that can be loaded in a real browser, exercised with Playwright, and trusted during staged integration.

## Scope

- tighten backend CORS configuration for known local frontend origins
- fix in-transaction order id generation for multi-order stop plans
- restore a passing backend test suite
- rerun browser and local build/test checks

## Acceptance criteria

- [ ] `GET /health` returns healthy on the local backend
- [ ] frontend loads successfully on the local dev port
- [ ] Playwright can load setup data from the cockpit UI
- [ ] backend `pytest` passes
- [ ] frontend lint, tests, and build pass

## Risks / constraints

- local ports can already be occupied by unrelated services
- the current workflow still depends on manual local process management until scripts are expanded further
