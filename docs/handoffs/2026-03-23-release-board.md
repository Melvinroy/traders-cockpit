# Release Board

Use this board to track the current promotion program from feature branches through staging and into `main`.

| Tranche | Branch | PR | Validation | Decision / Notes |
| --- | --- | --- | --- | --- |
| Release prep consolidation | `codex/feature-release-prep` | merged via integration | local lint/test/build, backend Ruff/Black/pytest, browser QC on isolated stack | prepared the clean candidate before integration promotion |
| Integration promotion candidate | `codex/feature-integration-promote-release-prep` | [#10](https://github.com/Melvinroy/traders-cockpit/pull/10) | frontend CI green, backend CI initially blocked on Black | merged into `codex/integration-app` after blocker fix |
| Integration Black blocker | `codex/bugfix-integration-black-ci` | folded into PR #10 head | backend Ruff, Black check, pytest | documented blocker; actual delivery path was the integration-promotion branch |
| Staged QC hardening | `codex/bugfix-qc-stable-symbol` | [#11](https://github.com/Melvinroy/traders-cockpit/pull/11) | `run-qc.ps1 -StartStack` on deterministic paper stack, refreshed Playwright artifacts | merged into `codex/integration-app` |
| Promotion to `main` | `codex/integration-app` | [#12](https://github.com/Melvinroy/traders-cockpit/pull/12) | promotion PR includes validation, known gaps, env/schema notes, rollback | open |

## Merge Sequence

1. Implement and validate on a dedicated `codex/*` branch.
2. Merge into `codex/integration-app`.
3. Run staged QC on integration and refresh required browser artifacts.
4. Open the promotion PR from `codex/integration-app` to `main`.
5. After merge to `main`, close linked issue docs and prune merged branches.
