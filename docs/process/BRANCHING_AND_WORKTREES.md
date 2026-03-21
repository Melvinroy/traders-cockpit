# Branching And Worktrees

## Branch Naming

- `codex/feature-short-name`
- `codex/bugfix-short-name`
- `codex/refactor-short-name`

## Promotion Path

- feature branch -> `codex/integration-app` -> `main`

## Branch Retention

- keep `main` and `codex/integration-app`
- keep only currently active unmerged `codex/*` branches
- delete merged feature branches after their promotion commit is reachable from `main`
- prune stale local tracking references regularly
- do not leave historical bugfix branches open once they are on `main`

## Working Notes

- Keep each branch limited to one coherent change.
- Create a worktree when local state is dirty or when isolation matters.
- Do not merge straight to `main` from a feature branch.
- After a staged promotion, close the linked issue doc and delete the merged feature branch.
