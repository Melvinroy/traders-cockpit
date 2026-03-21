# Component Matrix

This matrix tracks implementation status, reuse decisions, and remaining work for `traders-cockpit`.

| Component | Status | Current State | TradeCtrl Reuse | Remaining Work |
|---|---|---|---|---|
| Repo structure | Complete | Monorepo with frontend, backend, docs, scripts, CI, and release docs | Reused workflow shape and repo hygiene conventions | None |
| Git/GitHub workflow | Complete | Issue-first, `codex/*`, staged promotion through `codex/integration-app` | Reused staged promotion discipline | Keep branch protections enabled in GitHub |
| Frontend cockpit shell | Complete | Working Next.js cockpit with the prototype sections wired | Reused process conventions, not UI code | Continue literal parity polish as needed |
| Stop protection and profit workflow | Complete | `S1`, `S1·S2`, `S1·S2·S3`, tranche coverage, runner flow, browser regressions | Adapted safety discipline, not implementation | Continue UX polish |
| Orders blotter and activity log | Partial | Functional and increasingly audit-friendly | Reused recovery-first conventions | More visual and audit-detail polish |
| FastAPI service | Complete | Core lifecycle, account, positions, orders, logs, and auth routes are present | Reused app-structure and safety patterns | Continue hosted hardening |
| Env/config bootstrapping | Complete | Root/backend `.env` bootstrapping with typed settings | Adapted from `TradeCtrl` config bootstrap and naming | Continue env parity when new hosted requirements appear |
| Auth/session handling | Partial | Session-backed login with seeded dev users and opaque cookie tokens | Adapted from `TradeCtrl` auth store and session model | Enforce auth on more routes when frontend login UX is ready |
| Broker mode and live gating | Complete | Paper-first, live explicitly gated | Reused `TradeCtrl` safety model and env names | Add deeper production operator checks if needed |
| Alpaca integration | Partial | Paper/live config and adapter scaffolding exist | Reuse adapter shape, env names, and controller conventions from `TradeCtrl` | Deeper real-broker reconciliation and hosted validation |
| Market data normalization | Partial | Setup contract is normalized for the cockpit UI | Reused provider/env naming conventions | More provider-specific validation |
| Trading database | Complete | Dedicated `traders-cockpit` Postgres DB and Alembic history | Kept separate by design | None |
| Auth/session database | Complete | Dedicated local auth/session store for `traders-cockpit` | Reused `TradeCtrl` storage pattern, not the same file/DB | Consider moving to Postgres-backed auth later if desired |
| Redis/WebSocket backbone | Partial | Redis-backed fanout with normalized websocket events | Reused realtime hardening conventions | More hosted multi-instance validation |
| Deployment assets | Complete | Dockerfiles, Render blueprint, hosted env validation scripts | Reused hosted-env/safety discipline | Deploy real public environments |

## Reuse Boundaries

### Reuse As-Is Or Nearly As-Is

- Env naming and bootstrap conventions
- Staged branch and promotion workflow
- Paper-first and live-gated safety defaults
- Session-backed auth shape and opaque cookie tokens

### Adapt, Do Not Copy Blindly

- Alpaca adapter/controller structure
- Auth/session implementation details
- Hosted environment and operator-auth readiness checks

### Keep Separate

- Postgres database and Alembic history
- Redis/pubsub channel namespace
- Orders, positions, and audit-log storage
- Frontend deployment envs and runtime state
