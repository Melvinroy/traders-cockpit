> Status: Open
> Branch: codex/feature-docker-local-paper-runtime
> Opened: 2026-03-22
> Closed:
> Closing Commit:

## Issue

The local personal-paper workflow still treated Docker as secondary and still allowed silent mock degradation for the real quote and broker execution path. That made localhost testing unreliable for personal paper trading and hid real Alpaca sequencing failures.

## Why it matters

- local usage should be validated on Docker + localhost, not hosted staging
- Alpaca paper quotes and broker order submission need to be the real source of truth for entry and exit actions
- the app must fail loudly when Alpaca quote or execution is unavailable instead of pretending the local paper path is healthy
- localhost startup needs to be repeatable even on machines that already run other stacks such as `TradeCtrl`

## Acceptance

- `docker-compose.yml` is the canonical local runtime for frontend, backend, Postgres, and Redis
- Docker-local personal-paper mode requires:
  - `BROKER_MODE=alpaca_paper`
  - `ALLOW_LIVE_TRADING=false`
  - `ALLOW_CONTROLLER_MOCK=false`
- Alpaca quote failures surface as explicit setup errors in real local paper mode
- Alpaca market/stop/limit/trailing/flatten broker calls fail loudly when broker execution is unavailable
- Docker-local startup scripts support stable localhost ports and fail clearly on conflicts
- Docker-local smoke validates:
  - backend mode is `alpaca_paper`
  - latest quote provenance is real Alpaca
  - broker order submission returns real `brokerOrderId`
  - frontend loads successfully on localhost
- entry submission is represented honestly when the market is closed and a broker position is not yet filled
