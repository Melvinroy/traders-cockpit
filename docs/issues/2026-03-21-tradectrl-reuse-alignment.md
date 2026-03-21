# Issue: TradeCtrl Reuse Alignment

## Summary

Align `traders-cockpit` with the mature `TradeCtrl` patterns where reuse is helpful, without coupling the two apps to the same database or runtime state.

## Scope

- Add the TradeCtrl reuse/separation decisions to the repo's component matrix.
- Reuse TradeCtrl-style env/config fields where they improve safety and hosted readiness.
- Replace the lightweight username-in-cookie auth flow with a real session-backed auth store.
- Keep `traders-cockpit` on its own database, Alembic history, Redis channels, and audit logs.

## Acceptance

- Repo docs clearly distinguish what is reused, adapted, and kept separate from `TradeCtrl`.
- Backend auth uses opaque session tokens, not raw usernames in cookies.
- Seeded local auth still works for development.
- Existing API tests still pass, with new coverage for the login/session flow.

## Out Of Scope

- Sharing the same Postgres database with `TradeCtrl`
- Replacing the existing trading data model with `TradeCtrl` tables
- Full production auth policy enforcement across every API route in this tranche
