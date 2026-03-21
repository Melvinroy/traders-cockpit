# Issue: Vercel Next.js Security Upgrade

## Summary
Vercel preview deployment for the `frontend/` app is blocked because the repo pins `next@15.1.2`, which Vercel now rejects as vulnerable during build.

## Scope
- Upgrade `next` and `eslint-config-next` to a secure patched 15.x release.
- Refresh the frontend lockfile.
- Keep the existing React and app code unchanged unless the newer Next.js release requires compatibility fixes.
- Re-run frontend QC locally before retrying the Vercel preview deployment.

## Acceptance
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- Vercel preview deployment succeeds against the hosted Render backend.
