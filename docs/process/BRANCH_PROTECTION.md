# Branch Protection

Apply these repository settings in GitHub for long-term staged delivery.

## Protected branches

- `main`
- `codex/integration-app`

## Rules for `codex/integration-app`

- require pull requests before merging
- require at least 1 approving review
- dismiss stale approvals on new commits
- require status checks to pass before merging
- require branches to be up to date before merging
- block force pushes
- block branch deletion

## Required checks for `codex/integration-app`

- `backend`
- `frontend`

## Rules for `main`

- require pull requests before merging
- require at least 1 approving review
- require status checks to pass before merging
- require branches to be up to date before merging
- restrict direct pushes
- block force pushes
- block branch deletion

## Required checks for `main`

- `backend`
- `frontend`

## Merge policy

- feature branches merge only into `codex/integration-app`
- `main` accepts promotions only from `codex/integration-app`
- emergency hotfixes still use a scoped `codex/bugfix-*` branch and must be promoted through `codex/integration-app` unless production recovery time makes that impossible
