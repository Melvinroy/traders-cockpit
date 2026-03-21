> Status: Closed (legacy backfill)
> Branch: historical / pre-lifecycle-header
> Opened: 2026-03-20
> Closed: 2026-03-22
> Closing Commit: Legacy backfill during repo hygiene; historical promotion commit predates required lifecycle headers
# Frontend Reliability And UI Fidelity Recovery

GitHub issue: #8

## Problem

The local frontend URL is not reliable enough to share, and the current Next.js cockpit is materially simpler than the provided `UI.html` contract.

## Business value

This makes the frontend trustworthy in local QC and restores the actual product contract the repo was supposed to preserve.

## Scope

- harden frontend QC so dev and production verification do not corrupt each other
- fail browser smoke on runtime, asset, and console errors
- rebuild the frontend structure and styling to closely match `UI.html`
- preserve the prototype controls and cockpit interaction flow

## Acceptance criteria

- [ ] the frontend URL works after a clean QC run
- [ ] Playwright verifies `LOAD SETUP` without browser/runtime errors
- [ ] the rendered cockpit is materially aligned with `UI.html`

