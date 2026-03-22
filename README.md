<div align="center">
  <img src="docs/logo.svg" width="90" alt="Traders Cockpit Logo" />

  <h1>Traders Cockpit</h1>

  <p><strong>A production-grade swing trade management terminal.</strong><br/>
  Precision entry · Structured exits · Real-time position control · Built for serious traders.</p>

  <p>
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-00c8d4?style=flat-square" />
    <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-00d07a?style=flat-square&logo=python&logoColor=white" />
    <img alt="Node 22" src="https://img.shields.io/badge/node-22-00d07a?style=flat-square&logo=node.js&logoColor=white" />
    <img alt="Next.js" src="https://img.shields.io/badge/Next.js-15-white?style=flat-square&logo=next.js&logoColor=black" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" />
    <img alt="Docker" src="https://img.shields.io/badge/docker-compose-2496ED?style=flat-square&logo=docker&logoColor=white" />
  </p>

  <p>
    <a href="#-quick-start">Quick Start</a> ·
    <a href="#-the-interface">Interface</a> ·
    <a href="#-architecture">Architecture</a> ·
    <a href="#-configuration">Configuration</a> ·
    <a href="#-roadmap">Roadmap</a>
  </p>
</div>

---

## What is Traders Cockpit?

**Traders Cockpit** is an open-source, full-stack swing trade management terminal. It gives you a structured, server-side workflow for planning trades, sizing positions, managing stop ladders, and executing tranche-based profit plans — all in a single keyboard-driven dark UI.

Unlike a spreadsheet or a broker's default interface, Traders Cockpit enforces a **disciplined, repeatable process**:

- You define your **risk per trade** (e.g. 1% of equity), and the system sizes your position for you
- Stops and profit targets are calculated server-side and tracked as a **parent-child order tree**
- Every decision is logged to a **durable audit trail** with real-time WebSocket fanout
- Live trading is **off by default** — the full workflow runs in paper mode until you explicitly enable it

It is built for traders who want the control of a custom system without building one from scratch.

---

## ✨ Features

| | Feature | Details |
|---|---|---|
| 📐 | **Server-side risk sizing** | Equity × risk% ÷ per-share risk. No manual math. |
| 🎯 | **Structured stop ladder** | 1, 2, or 3 independent stop groups per position |
| 💰 | **Tranche profit plans** | Sell in up to 3 tranches at 1R, 2R, 3R, or manual targets |
| 🏃 | **Runner management** | Trailing stops ($ or %) for the runner tranche |
| ⚡ | **Real-time WebSocket** | Live price ticks, position and order updates pushed to the UI |
| 🔐 | **Session auth** | Cookie-based login with admin and trader roles |
| 🛡️ | **Safety guardrails** | Max notional cap, daily loss limit, max open positions, duplicate order prevention |
| 📋 | **Full audit log** | Every action — entry, stop, profit, flatten — is logged with timestamps |
| 🔌 | **Alpaca integration** | Paper and live execution via Alpaca API (live requires explicit opt-in) |
| 🐳 | **Docker-first** | One command to get the entire stack running locally |

---

## 🖥 The Interface

The UI is a dark terminal-style cockpit built with **Next.js + Tailwind + IBM Plex Mono**. It is designed to be information-dense without being cluttered.

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRADERS·COCKPIT   [$ AAPL ▸]  [LOAD]  [RESET]   $187.42  +1.3%   │
│  ─────────────────────────────────────────────────────────── PAPER  │
├──────────────────┬───────────────────────────┬──────────────────────┤
│  SETUP           │  ENTRY PANEL              │  ACTIVITY LOG        │
│  ─────────────   │  ─────────────────────    │  ─────────────────   │
│  Bid    187.38   │  Entry Price:  187.42     │  09:32 [EXEC]        │
│  Ask    187.46   │  Stop Ref:     LOD ▾      │  Buy 53sh AAPL       │
│  Last   187.42   │  Stop Price:   184.10     │  @ 187.42 (MKT)      │
│  LOD    184.10   │  Per-share R:  $3.32      │                      │
│  HOD    189.20   │  Shares:       53         │  09:32 [SYS]         │
│  ATR14  3.45     │  Dollar Risk:  $176       │  T1=18sh T2=18sh     │
│                  │  ─────────────────────    │  T3=17sh             │
│  R1     190.74   │  Tranches: 1  2  3        │                      │
│  R2     194.06   │                           │  09:31 [SYS]         │
│  R3     197.38   │  [PREVIEW]  [ENTER TRADE] │  Cockpit initialized │
│                  ├───────────────────────────┤                      │
│  POSITIONS       │  STOP PROTECTION          │                      │
│  ─────────────   │  ─────────────────────    │                      │
│  ● AAPL  PROT    │  Mode: ○1 ○2 ●3           │                      │
│                  │  S1 100%  S2 50%  S3 33%  │                      │
│                  │                           │                      │
│                  │  [EXECUTE STOPS]  [→ BE]  │                      │
│                  │  [■ FLATTEN]               │                      │
│                  ├───────────────────────────┤                      │
│                  │  PROFIT TAKING             │                      │
│                  │  ─────────────────────    │                      │
│                  │  T1: 18sh → 1R  $190.74   │                      │
│                  │  T2: 18sh → 2R  $194.06   │                      │
│                  │  T3: 17sh → RUN trail $2  │                      │
│                  │                           │                      │
│                  │  [EXECUTE PROFIT PLAN]    │                      │
└──────────────────┴───────────────────────────┴──────────────────────┘
```

**Panels:**

- **Setup** — Real-time quote data (bid/ask, LOD/HOD, ATR14, SMAs, RVOL), computed R-levels, and open position list
- **Entry Panel** — Set entry price, stop reference (LOD / ATR / manual), preview sizing, enter trade
- **Stop Protection** — Configure 1/2/3 independent stop groups, move all stops to breakeven, or flatten instantly
- **Profit Taking** — Configure up to 3 tranches with 1R/2R/3R/manual limit targets or a trailing stop runner
- **Activity Log** — Live-scrolling audit log with color-coded tags: `EXEC`, `SYS`, `WARN`, `CLOSE`

---

## 🚀 Quick Start

### Option 1 — Docker (recommended)

> Get the full stack running in under 2 minutes.

```bash
git clone https://github.com/your-org/traders-cockpit.git
cd traders-cockpit

# Copy and configure your environment
cp .env.example .env

# Start everything
docker compose --env-file .env up --build -d
```

| Service | URL |
|---|---|
| **Frontend** | http://127.0.0.1:3000 |
| **Backend API** | http://127.0.0.1:8000 |
| **API Docs (Swagger)** | http://127.0.0.1:8000/docs |

Default login: `admin` / `admin123!`

---

### Option 2 — Hybrid Local (fastest for development)

Run the frontend and backend as native processes, with only Postgres and Redis in Docker. This gives you instant hot reload on both sides.

```powershell
# Copy your personal-paper env file
Copy-Item .env.personal-paper.example .env.personal-paper.local
# Edit .env.personal-paper.local and add your Alpaca paper API keys

# Start the stack
.\scripts\dev\start-hybrid-local-personal-paper.ps1
```

| Service | URL |
|---|---|
| **Frontend** | http://127.0.0.1:3010 |
| **Backend API** | http://127.0.0.1:8010 |
| **PostgreSQL** | localhost:55432 |
| **Redis** | localhost:56379 |

To stop: `.\scripts\dev\stop-hybrid-local-personal-paper.ps1`

---

### Option 3 — Manual

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

> Requires PostgreSQL on `55432` and Redis on `56379`. See [docker-compose.yml](docker-compose.yml) to spin up just the infra.

---

## 🏗 Architecture

```
User Browser
     │  REST (HTTP)  /  WebSocket (ws://)
     ▼
┌─────────────┐                ┌──────────────────────┐
│  Next.js    │ ── REST ──▶   │  FastAPI Backend      │
│  Frontend   │ ◀── WS ─────  │  Python / Uvicorn     │
│ (port 3010) │               └──────────┬────────────┘
└─────────────┘                          │
                                ┌────────┴──────────┐
                                │                   │
                           ┌────▼────┐        ┌─────▼────┐
                           │Postgres │        │  Redis   │
                           │ :55432  │        │  :56379  │
                           └─────────┘        └──────────┘
                                                    │
                                             ┌──────▼──────┐
                                             │  Alpaca API │
                                             │ paper / live│
                                             └─────────────┘
```

**Stack:**

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | PostgreSQL 16 (SQLite fallback for tests) |
| Realtime | WebSocket + Redis pub/sub fanout |
| Broker | Alpaca Markets API (paper + live) |
| Auth | Cookie-based session auth (SQLite-backed) |
| Infra | Docker Compose, Render (hosted) |

**Key backend layers:**

- `app/api/` — Route handlers (auth, account, market, positions, trade)
- `app/services/cockpit.py` — All business logic: sizing, lifecycle, order hierarchy, safety checks
- `app/adapters/broker.py` — `PaperBrokerAdapter` (sim) and `AlpacaBrokerAdapter` (real execution)
- `app/adapters/market_data.py` — Alpaca/Polygon quotes with deterministic fallback
- `app/ws/manager.py` — Redis pub/sub fanout with single-process fallback

See [`docs/architecture/OVERVIEW.md`](docs/architecture/OVERVIEW.md) for a full breakdown.

---

## 📈 Trade Lifecycle

Every position flows through a strict server-side state machine:

```
idle
 └─▶ setup_loaded      (ticker loaded, market data fetched)
      └─▶ trade_entered  (entry order placed, tranches created)
           └─▶ protected   (stop orders active)
                ├─▶ P1_done      (first tranche sold)
                │    └─▶ P2_done   (second tranche sold)
                ├─▶ runner_only  (all limits filled, runner trailing)
                └─▶ closed       (all tranches exited or flattened)
```

**Order hierarchy** — every child order links back to the root entry:

```
ORD-0001  MKT  AAPL  53sh  FILLED     ← root entry order
├─ ORD-0002  STOP  18sh  @ 184.10  ACTIVE   ← stop group S1
├─ ORD-0003  STOP  35sh  @ 185.50  ACTIVE   ← stop group S2
├─ ORD-0004  LMT   18sh  @ 190.74  FILLED   ← T1 profit (1R)
├─ ORD-0005  LMT   18sh  @ 194.06  FILLED   ← T2 profit (2R)
└─ ORD-0006  TRAIL 17sh  trail $2  ACTIVE   ← T3 runner
```

---

## 🔧 Configuration

Copy `.env.example` to `.env` and set the values you need. Most have safe defaults.

### Core

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment: `development`, `staging`, `production` |
| `DATABASE_URL` | local postgres | PostgreSQL connection string |
| `REDIS_URL` | `redis://127.0.0.1:56379/0` | Redis connection string |
| `REDIS_CHANNEL_PREFIX` | `traders-cockpit` | Scopes WS pub/sub per environment |

### Auth

| Variable | Default | Description |
|---|---|---|
| `AUTH_REQUIRE_LOGIN` | `true` | Enforce login before access |
| `AUTH_ADMIN_USERNAME` | `admin` | Admin account username |
| `AUTH_ADMIN_PASSWORD` | `admin123!` | **Change this in production** |
| `AUTH_TRADER_USERNAME` | `trader` | Trader account username |
| `AUTH_SESSION_TTL_HOURS` | `24` | Session cookie lifetime |
| `AUTH_COOKIE_SAMESITE` | `lax` | Set `none` for cross-origin hosted deployments |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` in staging/production |

### Broker

| Variable | Default | Description |
|---|---|---|
| `BROKER_MODE` | `paper` | `paper`, `alpaca_paper`, or `alpaca_live` |
| `ALLOW_LIVE_TRADING` | `false` | Master switch for live execution |
| `LIVE_CONFIRMATION_TOKEN` | _(empty)_ | Required before live mode becomes effective |
| `ALPACA_API_KEY_ID` | _(empty)_ | Alpaca paper/live API key |
| `ALPACA_API_SECRET_KEY` | _(empty)_ | Alpaca paper/live API secret |
| `ALLOW_CONTROLLER_MOCK` | `true` | Fall back to sim if Alpaca credentials are missing |

### Risk Limits

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_ACCOUNT_EQUITY` | `100000` | Starting equity ($) |
| `DEFAULT_RISK_PCT` | `1` | Default risk per trade (%) |
| `MAX_POSITION_NOTIONAL_PCT` | `100` | Max position size as % of equity |
| `DAILY_LOSS_LIMIT_PCT` | `2` | Stop trading if daily loss exceeds this % |
| `MAX_OPEN_POSITIONS` | `6` | Maximum concurrent open positions |

---

## 🔌 Broker Modes

| Mode | Execution | Market Data | Use Case |
|---|---|---|---|
| `paper` | Simulated (instant fills) | Fallback local data | Deterministic dev & tests |
| `alpaca_paper` | Alpaca paper API | Real Alpaca quotes | Dev with real quotes, no real money |
| `alpaca_live` | Alpaca live API | Real Alpaca quotes | **Real money — requires explicit opt-in** |

> Live trading requires **all three**: `BROKER_MODE=alpaca_live` + `ALLOW_LIVE_TRADING=true` + `LIVE_CONFIRMATION_TOKEN=<token>`. Missing any one of them keeps execution in paper mode.

---

## 🧪 Testing

**Backend:**
```bash
cd backend
pytest -q
```

**Frontend:**
```bash
cd frontend
npm run lint      # ESLint
npm run test      # Vitest unit tests
npm run build     # TypeScript + production build check
```

**Full QC (backend + frontend + browser smoke):**
```powershell
.\scripts\dev\run-qc.ps1 -StartStack
```

Browser smoke artifacts land in `frontend/output/playwright/` and include baseline screenshots at key trade lifecycle stages.

---

## 🚢 Deployment

### Recommended hosted topology

| Service | Host |
|---|---|
| Frontend | [Vercel](https://vercel.com) |
| Backend | [Render](https://render.com) (Docker) |
| Database | Managed PostgreSQL (Render / Supabase / Neon) |
| Cache | Managed Redis (Render / Upstash) |

A `render.yaml` is included for one-click Render deployment.

**Important for cross-origin hosted deployments:**
```env
AUTH_COOKIE_SAMESITE=none
AUTH_COOKIE_SECURE=true
CORS_ORIGINS=https://your-frontend.vercel.app
```

Validate your hosted env before deploying:
```powershell
.\scripts\dev\check-hosted-env.ps1 -EnvFile ".env"
```

---

## 🗺 Roadmap

- [ ] **Real Alpaca paper reconciliation** — sync broker fills back into position state
- [ ] **Polygon technicals** — full ATR, SMAs, RVOL, days-to-cover from Polygon API
- [ ] **Position snapshots** — point-in-time state captures for post-trade review
- [ ] **Multi-instance Redis hardening** — battle-tested fanout for cloud deployments
- [ ] **Richer audit trail** — P&L per tranche, slippage tracking, trade journal export
- [ ] **Browser smoke expansion** — full lifecycle coverage in Playwright QC suite

---

## 🤝 Contributing

Contributions are welcome. This repo uses an issue-first, PR-first workflow.

1. **Open or link an issue** before starting any work
2. **Branch from** `codex/integration-app` using `codex/feature-*`, `codex/bugfix-*`, or `codex/refactor-*`
3. **Open a PR** back into `codex/integration-app` (not directly into `main`)
4. **Run the full QC path** before requesting review:
   ```powershell
   .\scripts\dev\run-qc.ps1 -StartStack
   ```
5. **Promote to `main`** only via a separate PR from `codex/integration-app → main`

See [`docs/process/WORKFLOW.md`](docs/process/WORKFLOW.md) for the full branching and release process.

---

## 📄 License

[MIT](LICENSE) — free to use, fork, and build on.

---

<div align="center">
  <sub>Built with precision. Trade with discipline.</sub><br/>
  <sub>
    <a href="docs/architecture/OVERVIEW.md">Architecture</a> ·
    <a href="docs/process/WORKFLOW.md">Workflow</a> ·
    <a href="docs/process/HOSTED_DEPLOYMENT.md">Deployment</a>
  </sub>
</div>
