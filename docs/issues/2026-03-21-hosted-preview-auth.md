> Status: Closed (legacy backfill)
> Branch: historical / pre-lifecycle-header
> Opened: 2026-03-21
> Closed: 2026-03-22
> Closing Commit: Legacy backfill during repo hygiene; historical promotion commit predates required lifecycle headers
## Issue

Hosted preview auth currently assumes a same-origin frontend/backend pairing. That blocks a Vercel preview frontend from staying authenticated against a separate backend domain because the auth cookie defaults to `SameSite=Lax`.

## Why it matters

- staged preview smoke needs a real public frontend URL
- the frontend calls the backend cross-origin in the recommended hosted topology
- cookie-backed auth must survive cross-origin requests in staging/preview

## Acceptance

- staging/preview can opt into `SameSite=None`
- staging/preview can opt into `Secure=true`
- local development remains on non-secure `Lax` defaults
- deployment docs note the hosted cookie requirement

