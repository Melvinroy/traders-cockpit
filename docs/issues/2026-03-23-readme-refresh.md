# README Refresh

> Status: In Progress
> Branch: `codex/refactor-readme-refresh`
> Opened: 2026-03-23
> Closed: -
> Closing Commit: -

## Problem

The repository README was still a thin engineering overview. It did not present Traders Cockpit clearly as a product, did not show current UI evidence, and did not fully reflect the integration branch's lifecycle, startup paths, validation expectations, and environment contract.

## Business value

A stronger README improves first-run success, makes the project legible to contributors and users, and reduces confusion around paper-vs-live safety, startup scripts, and the server-side trade lifecycle.

## Scope

- Rewrite `README.md` around the current product narrative and repo truth.
- Add stable README screenshots owned by the repo.
- Align linked architecture wording with the current lifecycle phases.

## Acceptance criteria

- [ ] README presents the cockpit as an open-source swing trade terminal with current feature and lifecycle details.
- [ ] README startup, auth, broker-mode, and testing sections match the current integration branch scripts and env defaults.
- [ ] README embeds current cockpit screenshots from repo-owned paths.
- [ ] `docs/architecture/OVERVIEW.md` no longer uses vague lifecycle wording that conflicts with the README.

## Risks / constraints

- `codex/integration-app` does not currently include the newer hybrid-local startup script, so the README must describe the startup paths that actually exist on this branch.
- The branch has mixed credential defaults across `.env.example`, `.env.personal-paper.example`, and `docker-compose.yml`; the README needs to describe that honestly instead of inventing a single default.
