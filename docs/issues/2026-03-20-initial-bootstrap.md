# Initial GitHub Bootstrap

## Problem

`traders-cockpit` exists only as a local prototype workspace and needs to become a real GitHub-ready repository with a staged branch model, monorepo structure, and baseline application scaffold.

## Business value

This creates the durable source-control foundation required for issue-first delivery, staged promotion, contributor onboarding, and future PR discipline.

## Scope

- Create the repository structure and process docs
- Add frontend and backend bootstrap code
- Initialize staged branches and prepare GitHub push flow
- Exclude local/generated artifacts from source control

## Acceptance criteria

- [ ] Local repo has `main`, `codex/integration-app`, and a scoped `codex/feature-*` branch history
- [ ] Initial scaffold is committed
- [ ] GitHub remote exists for `traders-cockpit`
- [ ] `main` and `codex/integration-app` are pushed

## Risks / constraints

- Current implementation still has known failing checks that should be fixed in follow-up work
- Initial bootstrap precedes full PR-based promotion because the remote does not exist yet
