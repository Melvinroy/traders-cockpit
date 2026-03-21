# Issue: Auth Enforcement And Login UX

## Summary

Harden sensitive API routes behind session auth and add a frontend login/logout flow so the cockpit no longer depends on permissive local defaults.

## Scope

- Protect account, positions, setup, and trade routes with session auth.
- Require websocket authentication when login is enabled.
- Add a frontend sign-in screen and session-aware logout control.
- Update browser QC scripts to authenticate before running cockpit flows.

## Acceptance

- Unauthenticated requests to protected routes return `401` when login is enabled.
- Login produces an opaque session cookie and `/api/auth/me` resolves the current user.
- Frontend displays a login panel when no valid session exists.
- Browser QC still passes using the login flow.
