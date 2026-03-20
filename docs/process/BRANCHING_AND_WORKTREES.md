# Branching And Worktrees

## Branch Naming

- `codex/feature-short-name`
- `codex/bugfix-short-name`
- `codex/refactor-short-name`

## Promotion Path

- feature branch -> `codex/integration-app` -> `main`

## Working Notes

- Keep each branch limited to one coherent change.
- Create a worktree when local state is dirty or when isolation matters.
- Do not merge straight to `main` from a feature branch.
