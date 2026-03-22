# CATALYST Trade Cockpit — Backend Architecture Prompt

## Context

I have a working paper-trading front end called **CATALYST / COCKPIT** built as a single HTML file. It currently runs entirely in browser memory with mock data. I need you to architect and build the full backend that powers this UI with real data, real broker connectivity, and persistent state. The front end is the contract — do not change it. Build everything behind it.

---

## What the UI Does (Full Functional Spec)

### 1. Header
- **Ticker input** — user types a symbol (e.g. AAPL), presses Enter or clicks LOAD SETUP
- **Live price display** — top right shows `SYMBOL · PRICE · DELTA · DELTA%` updating in real time
- **State badge** — shows current trade phase: IDLE → SETUP LOADED → TRADE ENTERED → PROTECTED → P1 DONE → P2 DONE → RUNNER ONLY → CLOSED
- **PAPER badge** — toggleable between PAPER and LIVE mode

### 2. Left Panel — Setup Parameters
Populated when a ticker is loaded. Must fetch and display:

**Quote section**
- Bid, Ask, Suggested Entry (midpoint)

**Stop Levels**
- Low of Day (LoD)
- ATR (14-period)
- Final Stop (driven by stop reference selector)

**Risk Sizing**
- Account Equity (user setting, persisted)
- Risk % (user setting, persisted, default 1%)
- Dollar Risk = Equity × Risk%
- Per-Share Risk = Entry − Final Stop
- Calculated Shares = floor(Dollar Risk / Per-Share Risk)

**Reference section**
- 10 SMA
- 50 SMA
- 200 MA + direction (rising/declining based on prev value)
- ATR Extension from 50MA = (Entry − SMA50) / ATR → green <4x, amber 4–8x, red ≥8x
- RVOL (Relative Volume) → green ≥2x, red <2x
- Ext from 10 MA = (Entry − SMA10) / SMA10 × 100% → red >10%, green otherwise
- Days to Cover (short interest / avg daily volume)

**Open Positions section** (bottom of left panel)
- Shows all currently active positions as compact cards
- Each card: Symbol, PnL (live), Entry, Live Price, STOP SET badge (green/red), PROFIT ON badge (cyan/grey)
- Clicking a card loads that position into all main panels

### 3. Middle Top — Trade Entry

**Entry Price** — editable, defaults to midpoint. Changing it recalculates shares.

**Shares to Buy** — calculated, read-only display.

**Stop Reference selector** — 3 modes:
- `LoD` — uses Low of Day as stop
- `ATR` — uses Entry − (ATR × multiplier), multiplier is editable
- `Manual` — user types in a stop price

**Buttons:**
- `PREVIEW` — logs the trade details without executing
- `ENTER TRADE` — creates the position, splits shares into tranches, records MKT entry order

### 4. Middle Mid — Stop Protection

**Header controls (grid-aligned with Profit Taking):**
- `STOPS` label
- `S1` — single stop covering all shares
- `S1·S2` — two stops, shares split ~50/50
- `S1·S2·S3` — three stops, shares split ~33/33/34
- `EXECUTE` button — amber until mode selected, turns green, executes all stop orders when clicked

**Stop Plan rows** (one per stop):
- Label (S1/S2/S3)
- Mode toggle: STOP ↔ BE (breakeven)
- % input — how far below entry (as % of entry-to-stop range)
- Computed stop price
- Share quantity
- Status: PREVIEW → ACTIVE after execute

**Risk actions:**
- `ALL → BE` — moves all active stops to entry price
- `⬛ FLATTEN` — market sells all active tranches, cancels all stops, closes position

### 5. Middle Bottom — Profit Taking

**Header controls (grid-aligned with Stop Protection):**
- `TRANCHES` label
- `P1` — single tranche, 100%
- `P1·P2` — two tranches
- `P1·P2·P3` — three tranches
- `EXECUTE` button — executes ALL active tranches simultaneously when clicked

**Exit Plan rows** (one per tranche):
- Tranche label (P1/P2/P3)
- Mode toggle: LIMIT ↔ RUNNER
- % split (editable, auto-balances to 100%)
- Target price:
  - LIMIT mode: 1R / 2R / 3R / Manual — R = per-share risk distance
  - RUNNER mode: trail input ($ or %) + unit toggle
- Share quantity
- ✓ indicator after execution

**Below exit plan:**
- Exits section — tranche cards showing sold/active/runner status
- Position Summary — total shares, active, sold, entry, notional
- Orders blotter — full order table with parent/child hierarchy

### 6. Right Panel — Activity Log
- Timestamped entries prepended to top
- Tag types: INFO (blue), EXEC (green), WARN (amber), CLOSE (red), SYS (purple)
- CLR button to clear log

---

## Order Hierarchy

Every trade creates a root MKT order. All child orders link to it:

```
ORD-0001  MKT   287sh  213.88  FILLED   AAPL        ← root entry
├─ ORD-0002  STOP   95sh  212.73  ACTIVE   S1         ← stop child
├─ ORD-0003  STOP   95sh  212.73  ACTIVE   S2
├─ ORD-0004  STOP   97sh  212.70  ACTIVE   S3
├─ ORD-0005  LMT    94sh  217.36  FILLED   T1  (P1)  ← profit child
├─ ORD-0006  LMT    94sh  220.84  FILLED   T2  (P2)
└─ ORD-0007  TRAIL  99sh  211.88  ACTIVE   T3  (runner)
```

When a tranche is sold, all STOP orders covering that tranche reduce qty. If qty hits 0 → CANCELED.

---

## Trade State Machine

```
idle
  └→ setup_loaded       (ticker loaded)
       └→ trade_entered  (ENTER TRADE clicked)
            └→ protected  (stops executed)
                 ├→ P1_done      (P1 profit taken)
                 │    ├→ P2_done
                 │    │    └→ runner_only
                 │    └→ runner_only
                 └→ closed        (FLATTEN or all tranches sold)
```

---

## Data Requirements Per Ticker

The backend must provide these fields for any symbol:

```json
{
  "symbol": "AAPL",
  "bid": 213.85,
  "ask": 213.92,
  "last": 213.88,
  "lod": 210.40,
  "hod": 215.10,
  "prev_close": 212.50,
  "atr14": 3.20,
  "sma10": 211.20,
  "sma50": 198.40,
  "sma200": 195.20,
  "sma200_prev": 194.80,
  "rvol": 1.8,
  "days_to_cover": 2.4
}
```

---

## Backend Architecture Requirements

### Tech Stack (recommended)
- **FastAPI** (Python) — REST + WebSocket API
- **PostgreSQL** — persistent position, order, and session storage
- **Redis** — real-time price pub/sub, session caching
- **Alpaca Markets API** — broker connectivity (paper + live), market data
- **Polygon.io** — supplementary market data (RVOL, SMA, ATR, Days to Cover)

### API Endpoints Required

#### Market Data
```
GET  /api/setup/{symbol}          → returns full setup object (quote + technicals)
WS   /ws/price/{symbol}           → real-time price stream (bid/ask/last/delta)
```

#### Trade Management
```
POST /api/trade/enter             → submit MKT entry order
POST /api/trade/stops             → place stop orders (S1/S2/S3 config)
POST /api/trade/profit            → execute all profit-taking tranches
POST /api/trade/flatten           → market sell all, cancel all stops
POST /api/trade/move_to_be        → move all stops to entry price
```

#### Position State
```
GET  /api/positions               → all open positions with full state
GET  /api/positions/{symbol}      → single position state
GET  /api/orders/{symbol}         → order blotter for symbol
PUT  /api/positions/{symbol}/stop → modify stop price/mode
```

#### Account
```
GET  /api/account                 → equity, buying power, risk settings
PUT  /api/account/settings        → update risk%, account equity
```

### Database Schema

**positions**
```sql
id, symbol, phase, entry_price, shares, stop_ref, stop_price,
tranche_count, t1_pct, t2_pct, t3_pct,
tranche_modes (jsonb),   -- [{mode, target, trail, trailUnit}]
stop_modes (jsonb),      -- [{mode, pct}]
root_order_id, created_at, updated_at, closed_at
```

**orders**
```sql
id, broker_order_id, symbol, type (MKT/LMT/STOP/TRAIL),
qty, orig_qty, price, status (ACTIVE/FILLED/CANCELED/MODIFIED),
tranche_label, covered_tranches (jsonb), parent_id,
created_at, filled_at, fill_price
```

**account_settings**
```sql
id, equity, risk_pct, mode (paper/live), updated_at
```

**trade_log**
```sql
id, symbol, tag (info/exec/warn/close/sys), message, created_at
```

### WebSocket Protocol

The frontend connects to `WS /ws/cockpit` and expects:

```json
// Price tick
{ "type": "price", "symbol": "AAPL", "bid": 213.85, "ask": 213.92, "last": 213.88, "delta": 0.03, "delta_pct": 0.01 }

// Order update
{ "type": "order_update", "order_id": "ORD-0002", "status": "FILLED", "fill_price": 212.73 }

// Position update
{ "type": "position_update", "symbol": "AAPL", "phase": "protected", "pnl": 68.88 }
```

### Broker Integration (Alpaca)

Map cockpit actions to Alpaca API calls:

| Cockpit Action | Alpaca Call |
|---|---|
| ENTER TRADE | `POST /v2/orders` type=market |
| Stop (S1 mode) | `POST /v2/orders` type=stop, linked to parent via client_order_id |
| Profit LMT | `POST /v2/orders` type=limit |
| RUNNER (trail) | `POST /v2/orders` type=trailing_stop, trail_price or trail_percent |
| ALL → BE | `PATCH /v2/orders/{id}` stop_price=entry |
| FLATTEN | `DELETE /v2/positions/{symbol}` |
| Cancel stop | `DELETE /v2/orders/{id}` |

Use Alpaca's **bracket order** or **OCA (One Cancels All)** group for linking stop + limit to the entry order.

### Risk Controls (non-negotiable)

1. **Max position size check** — reject if notional > account_equity × 20%
2. **Daily loss limit** — halt trading if realized PnL < −(equity × 2%)
3. **Duplicate order prevention** — check open orders before placing new ones
4. **Stop price validation** — reject stops above entry or below 50% of entry
5. **Paper/Live mode gate** — all live order calls require `mode=live` flag + confirmation token

### Computed Fields (backend responsibility)

These must be computed server-side, not in the browser:

- **R-multiples**: 1R = entry + perShareRisk, 2R = entry + 2×perShareRisk, 3R = entry + 3×perShareRisk
- **ATR Extension**: (entry − SMA50) / ATR14
- **Ext from 10MA**: (entry − SMA10) / SMA10 × 100
- **RVOL**: current volume / avg volume at this time of day (VWAP-adjusted)
- **Days to Cover**: short interest / avg daily volume
- **Stop price from %**: entry − (entry−finalStop) × pct/100
- **Trail stop price**: livePrice − trailAmount ($ mode) or livePrice × (1 − trail%) (% mode)
- **Per-share risk**: entry − finalStop
- **Shares**: floor(dollarRisk / perShareRisk)
- **Tranche qty splits**: floor(shares × pct/100), last tranche gets remainder

### Market Data Sources

| Field | Source |
|---|---|
| Bid/Ask/Last | Alpaca real-time stream |
| LoD/HoD | Alpaca bars (1D) |
| ATR14 | Compute from Alpaca 14-day daily bars |
| SMA10/50/200 | Compute from Alpaca daily bars |
| RVOL | Polygon.io snapshot or compute from Alpaca volume data |
| Days to Cover | Polygon.io short interest endpoint |

---

## Session & Persistence

- On page load: `GET /api/positions` → restore all open positions into UI state
- On trade enter: immediately persist to DB
- On stop/profit execute: update DB atomically with order records
- On price tick: update `livePrice` on position record every 5s
- On browser close: positions remain in DB, restored on next open

---

## Front End Integration Notes

The existing HTML file uses these global JS functions that must be called by the backend responses:

- `loadSetup()` → triggers `GET /api/setup/{symbol}`
- `enterTrade()` → triggers `POST /api/trade/enter`
- `commitStopMode()` → triggers `POST /api/trade/stops`
- `commitProfitPlan()` → triggers `POST /api/trade/profit`
- `flattenPosition()` → triggers `POST /api/trade/flatten`
- `allToBE()` → triggers `PUT` on all active stop orders
- `tickPrice()` → replaced by WebSocket price stream

Replace the `MOCK` data object and `setTimeout` price simulation with real API calls. Keep all rendering functions (`renderSetupPanel`, `renderOrders`, `renderExitPlan`, etc.) intact — they just need to receive real data in the same shape.

The state object shape the front end expects:

```javascript
state = {
  symbol, phase, livePrice,
  setup: { entry, finalStop, r1, r2, r3, shares, dollarRisk, perShareRisk },
  mock: { bid, ask, lod, atr, sma10, sma50, sma200, sma200prev, rvol, dtc },
  tranches: [{ id, qty, stop, target, status, mode, trail, trailUnit, label }],
  orders: [{ id, type, qty, origQty, price, status, tranche, coveredTranches, parentId }],
  trancheModes: [{ mode, trail, trailUnit, target, manualPrice }],
  stopModes: [{ mode, pct }],
  rootOrderId, stopMode, trancheCount, accountEquity, riskPct
}
```

---

## Deliverables Expected from Claude Code / Codex

1. `backend/` — FastAPI app with all endpoints
2. `backend/broker/alpaca.py` — Alpaca order management client
3. `backend/data/market.py` — market data fetcher (Alpaca + Polygon)
4. `backend/db/models.py` — SQLAlchemy models
5. `backend/db/migrations/` — Alembic migrations
6. `backend/ws/price_stream.py` — WebSocket price broadcaster
7. `backend/risk/controls.py` — pre-trade risk checks
8. `frontend/Cockpit.html` — updated to call real API (replace MOCK + setTimeout)
9. `docker-compose.yml` — FastAPI + PostgreSQL + Redis
10. `CLAUDE.md` — development notes for AI-assisted iteration
11. `.env.example` — required environment variables

---

## Environment Variables Required

```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets   # or live
POLYGON_API_KEY=
DATABASE_URL=postgresql://<db-user>:<db-password>@<db-host>:5432/<db-name>
REDIS_URL=redis://<redis-host>:6379/0
ACCOUNT_EQUITY=100000
DEFAULT_RISK_PCT=1.0
MODE=paper   # paper | live
```

---

## Notes for the AI Agent

- Start with **paper trading mode** — do not touch live broker until paper is fully tested
- The front end HTML file is the source of truth for UI behavior — match it exactly
- Use `client_order_id` in Alpaca to map broker orders back to cockpit order IDs (ORD-0001 etc.)
- The order blotter parent/child hierarchy must be preserved — use `parentId` field
- RVOL calculation: `current_volume / (avg_daily_volume × (minutes_elapsed / 390))`
- ATR calculation: Wilder's smoothing over 14 periods using daily OHLC bars
- All monetary values are USD, 2 decimal places
- All share quantities are integers (floor division)
- Tranche qty splits must sum exactly to total shares — last tranche gets the remainder


---

## Reference UI — Cockpit.html (Full Source)

The following is the complete current front end. This is your source of truth for all UI behavior, state shape, rendering logic, and interaction patterns. Study it carefully before building anything.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CATALYST · Trade Cockpit</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
  :root {
    --bg0:#0a0c0f;--bg1:#0f1218;--bg2:#141820;--bg3:#1c2230;--bg4:#242d3d;
    --border:#1e2a3a;--border2:#2a3a50;
    --text0:#e8edf5;--text1:#a8b8cc;--text2:#6a7d95;--text3:#3d5068;
    --green:#00d07a;--green-dim:#00874e;--green-bg:rgba(0,208,122,0.08);
    --red:#ff4060;--red-dim:#a02030;--red-bg:rgba(255,64,96,0.08);
    --amber:#f5a623;--amber-bg:rgba(245,166,35,0.08);
    --blue:#4a9eff;--blue-bg:rgba(74,158,255,0.08);
    --cyan:#00c8d4;--purple:#9b7fe8;
    --mono:'IBM Plex Mono',monospace;--sans:'IBM Plex Sans',sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg0);color:var(--text0);font-family:var(--sans);font-size:13px;min-height:100vh;overflow-x:hidden;}
  .header{background:var(--bg1);border-bottom:1px solid var(--border);padding:0 20px;height:52px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100;}
  .logo{font-family:var(--mono);font-size:13px;font-weight:600;letter-spacing:0.2em;color:var(--cyan);white-space:nowrap;}
  .logo span{color:var(--text2);font-weight:400;}
  .divider-v{width:1px;height:24px;background:var(--border2);flex-shrink:0;}
  .ticker-bar{display:flex;align-items:center;gap:8px;}
  .ticker-input-wrap{position:relative;display:flex;align-items:center;}
  .ticker-prefix{font-family:var(--mono);font-size:12px;color:var(--text2);background:var(--bg3);border:1px solid var(--border2);border-right:none;padding:0 8px;height:32px;display:flex;align-items:center;border-radius:4px 0 0 4px;}
  #tickerInput{font-family:var(--mono);font-size:14px;font-weight:600;letter-spacing:0.1em;color:var(--text0);background:var(--bg3);border:1px solid var(--border2);border-left:none;padding:0 10px;height:32px;width:80px;outline:none;text-transform:uppercase;border-radius:0 4px 4px 0;transition:border-color 0.15s;}
  #tickerInput:focus{border-color:var(--cyan);}
  .btn{font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:0.05em;border:1px solid;padding:0 12px;height:32px;cursor:pointer;border-radius:3px;transition:all 0.12s;white-space:nowrap;display:inline-flex;align-items:center;gap:5px;}
  .btn:disabled{opacity:0.3;cursor:not-allowed;}
  .btn-cyan{background:rgba(0,200,212,0.1);border-color:var(--cyan);color:var(--cyan);}
  .btn-cyan:hover:not(:disabled){background:rgba(0,200,212,0.2);}
  .btn-green{background:var(--green-bg);border-color:var(--green);color:var(--green);}
  .btn-green:hover:not(:disabled){background:rgba(0,208,122,0.18);}
  .btn-red{background:var(--red-bg);border-color:var(--red);color:var(--red);}
  .btn-red:hover:not(:disabled){background:rgba(255,64,96,0.18);}
  .btn-amber{background:var(--amber-bg);border-color:var(--amber);color:var(--amber);}
  .btn-ghost{background:var(--bg3);border-color:var(--border2);color:var(--text1);}
  .btn-ghost:hover:not(:disabled){background:var(--bg4);border-color:var(--text2);}
  .btn-purple{background:rgba(155,127,232,0.1);border-color:var(--purple);color:var(--purple);}
  .btn-purple:hover:not(:disabled){background:rgba(155,127,232,0.2);}
  .badge{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.12em;padding:2px 7px;border-radius:2px;text-transform:uppercase;}
  .badge-paper{background:rgba(245,166,35,0.15);color:var(--amber);border:1px solid rgba(245,166,35,0.3);}
  .live-price{font-family:var(--mono);font-size:18px;font-weight:600;color:var(--text0);margin-left:auto;}
  .live-price .change{font-size:12px;margin-left:8px;}
  .live-price .up{color:var(--green);}
  .live-price .dn{color:var(--red);}
  .workspace{display:grid;grid-template-columns:300px 1fr 280px;grid-template-rows:auto auto 1fr;gap:1px;background:var(--border);height:calc(100vh - 52px);}
  .panel{background:var(--bg1);overflow:auto;}
  .panel-header{background:var(--bg2);border-bottom:1px solid var(--border);padding:8px 14px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10;}
  .panel-title{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.18em;color:var(--text2);text-transform:uppercase;}
  .panel-body{padding:12px 14px;}
  .setup-panel{grid-column:1;grid-row:1/4;}
  .kv-group{margin-bottom:14px;}
  .kv-group-label{font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.2em;color:var(--text3);text-transform:uppercase;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid var(--border);}
  .kv-row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid rgba(30,42,58,0.5);}
  .kv-label{font-family:var(--mono);font-size:10px;color:var(--text2);}
  .kv-val{font-family:var(--mono);font-size:11px;font-weight:500;color:var(--text0);}
  .kv-val.green{color:var(--green);}
  .kv-val.red{color:var(--red);}
  .kv-val.amber{color:var(--amber);}
  .kv-val.cyan{color:var(--cyan);}
  .entry-panel{grid-column:2;grid-row:1;overflow:hidden;}
  .entry-panel .panel-body{padding:12px 20px;height:calc(100% - 37px);box-sizing:border-box;overflow:hidden;}
  .protect-panel{grid-column:2;grid-row:2;}
  .manage-panel{grid-column:2;grid-row:3;display:flex;flex-direction:column;}
  .tranche-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px;}
  .tranche-card{background:var(--bg2);border:1px solid var(--border2);border-radius:4px;padding:10px 12px;transition:border-color 0.15s;}
  .tranche-card.active{border-color:var(--green-dim);}
  .tranche-card.sold{border-color:var(--border);opacity:0.5;}
  .tranche-card.canceled{border-color:var(--border);opacity:0.4;}
  .tranche-label{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.15em;color:var(--text3);text-transform:uppercase;margin-bottom:6px;}
  .tranche-qty{font-family:var(--mono);font-size:16px;font-weight:600;color:var(--text0);margin-bottom:4px;}
  .tranche-stop{font-family:var(--mono);font-size:10px;color:var(--red);margin-bottom:3px;}
  .tranche-target{font-family:var(--mono);font-size:10px;color:var(--green);}
  .status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:5px;}
  .status-active .status-dot{background:var(--green);box-shadow:0 0 5px var(--green);}
  .status-sold .status-dot{background:var(--text3);}
  .status-canceled .status-dot{background:var(--red-dim);}
  .tranche-status{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;display:flex;align-items:center;margin-top:6px;}
  .status-active{color:var(--green);}
  .status-sold{color:var(--text3);}
  .status-canceled{color:var(--red-dim);}
  .orders-table{width:100%;border-collapse:collapse;font-family:var(--mono);}
  .orders-table th{font-size:9px;font-weight:600;letter-spacing:0.12em;color:var(--text3);text-transform:uppercase;text-align:left;padding:6px 8px;border-bottom:1px solid var(--border2);white-space:nowrap;}
  .orders-table td{font-size:11px;color:var(--text1);padding:5px 8px;border-bottom:1px solid rgba(30,42,58,0.6);white-space:nowrap;}
  .orders-table tr:hover td{background:var(--bg3);}
  .order-status-ACTIVE{color:var(--green);font-weight:600;}
  .order-status-FILLED{color:var(--text2);}
  .order-status-CANCELED{color:var(--text3);text-decoration:line-through;}
  .order-status-PENDING{color:var(--amber);}
  .order-status-MODIFIED{color:var(--cyan);font-weight:600;}
  .log-panel{grid-column:3;grid-row:1/4;display:flex;flex-direction:column;}
  .log-body{flex:1;overflow-y:auto;padding:10px 12px;}
  .log-entry{display:flex;gap:8px;padding:5px 0;border-bottom:1px solid rgba(30,42,58,0.5);animation:fadeIn 0.3s ease;}
  @keyframes fadeIn{from{opacity:0;transform:translateY(-4px);}to{opacity:1;transform:translateY(0);}}
  .log-time{font-family:var(--mono);font-size:9px;color:var(--text3);white-space:nowrap;padding-top:1px;}
  .log-msg{font-family:var(--mono);font-size:10px;color:var(--text1);line-height:1.5;}
  .log-msg .tag{display:inline-block;font-size:8px;font-weight:600;padding:1px 5px;border-radius:2px;margin-right:4px;text-transform:uppercase;letter-spacing:0.08em;}
  .tag-info{background:var(--blue-bg);color:var(--blue);}
  .tag-exec{background:var(--green-bg);color:var(--green);}
  .tag-warn{background:var(--amber-bg);color:var(--amber);}
  .tag-close{background:var(--red-bg);color:var(--red);}
  .tag-sys{background:rgba(155,127,232,0.12);color:var(--purple);}
  .state-display{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.12em;padding:3px 8px;border-radius:2px;text-transform:uppercase;}
  .state-idle{background:rgba(106,125,149,0.15);color:var(--text2);border:1px solid var(--border2);}
  .state-setup_loaded{background:rgba(74,158,255,0.15);color:var(--blue);border:1px solid rgba(74,158,255,0.3);}
  .state-trade_entered{background:rgba(245,166,35,0.15);color:var(--amber);border:1px solid rgba(245,166,35,0.3);}
  .state-protected{background:rgba(0,208,122,0.15);color:var(--green);border:1px solid rgba(0,208,122,0.3);}
  .state-P1_done{background:rgba(0,200,212,0.15);color:var(--cyan);border:1px solid rgba(0,200,212,0.3);}
  .state-P2_done{background:rgba(155,127,232,0.15);color:var(--purple);border:1px solid rgba(155,127,232,0.3);}
  .state-runner_only{background:rgba(155,127,232,0.2);color:var(--purple);border:1px solid var(--purple);}
  .state-closed{background:rgba(255,64,96,0.15);color:var(--red);border:1px solid rgba(255,64,96,0.3);}
  .empty-state{padding:30px 14px;text-align:center;color:var(--text3);font-family:var(--mono);font-size:11px;}
  .empty-icon{font-size:28px;margin-bottom:10px;opacity:0.4;}
  ::-webkit-scrollbar{width:4px;height:4px;}
  ::-webkit-scrollbar-track{background:transparent;}
  ::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px;}
  .pos-summary{display:flex;gap:16px;font-family:var(--mono);font-size:11px;background:var(--bg3);border:1px solid var(--border2);border-radius:3px;padding:8px 12px;margin-bottom:12px;}
  .pos-item{display:flex;flex-direction:column;gap:2px;}
  .pos-item-label{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:0.1em;}
  .pos-item-val{font-size:13px;font-weight:600;color:var(--text0);}
  .pos-item-val.green{color:var(--green);}
  .section-label{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.15em;color:var(--text3);text-transform:uppercase;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border);}
  .ticker-symbol-large{font-family:var(--mono);font-size:22px;font-weight:600;color:var(--text0);letter-spacing:0.05em;}
  .flash{animation:flash 0.4s ease;}
  @keyframes flash{0%{opacity:1;}25%{opacity:0.3;}100%{opacity:1;}}
  .tranche-count-btn{font-family:var(--mono);font-size:10px;font-weight:600;height:24px;padding:0 8px;border:1px solid var(--border2);background:var(--bg3);color:var(--text2);cursor:pointer;border-radius:2px;transition:all 0.12s;display:flex;align-items:center;justify-content:center;white-space:nowrap;}
  .tranche-count-btn:hover{border-color:var(--text1);color:var(--text0);}
  .tranche-count-btn.active{background:rgba(0,208,122,0.12);border-color:var(--green);color:var(--green);}
  .mode-toggle{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.08em;padding:2px 7px;border-radius:2px;cursor:pointer;border:1px solid;transition:all 0.12s;text-transform:uppercase;}
  .mode-toggle.limit{background:var(--green-bg);border-color:var(--green-dim);color:var(--green);}
  .mode-toggle.runner{background:rgba(155,127,232,0.12);border-color:var(--purple);color:var(--purple);}
  .trail-input{font-family:var(--mono);font-size:11px;font-weight:600;background:var(--bg3);border:1px solid var(--border2);color:var(--purple);height:22px;width:24px;padding:0 3px;outline:none;border-radius:2px 0 0 2px;text-align:right;}
  .trail-unit-toggle{font-family:var(--mono);font-size:10px;font-weight:600;background:var(--bg3);border:1px solid var(--border2);border-left:none;color:var(--purple);height:22px;width:18px;padding:0;text-align:center;cursor:pointer;border-radius:0 2px 2px 0;transition:background 0.12s;}
  .trail-unit-toggle:hover{background:var(--bg4);}
  /* ARM button */
  .arm-btn{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.1em;height:22px;padding:0 10px;border-radius:2px;cursor:pointer;border:1px solid rgba(245,166,35,0.5);background:rgba(245,166,35,0.08);color:var(--amber);transition:all 0.15s;}
  .arm-btn.armed{background:rgba(255,64,96,0.2);border-color:var(--red);color:var(--red);box-shadow:0 0 8px rgba(255,64,96,0.3);}
  .arm-btn:hover:not(.armed){background:rgba(245,166,35,0.15);border-color:var(--amber);}
  /* open positions */
  .op-section-label{font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.18em;color:var(--text3);text-transform:uppercase;padding:10px 0 6px;border-bottom:1px solid var(--border);margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;}
  .op-card{background:var(--bg2);border:1px solid var(--border2);border-radius:4px;margin-bottom:6px;overflow:hidden;cursor:pointer;transition:border-color 0.15s;}
  .op-card:hover{border-color:var(--cyan);}
  .op-card.expanded{border-color:var(--cyan);}
  .op-card-header{padding:8px 10px;}
  .op-top-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}
  .op-symbol{font-family:var(--mono);font-size:15px;font-weight:600;color:var(--text0);letter-spacing:0.05em;}
  .op-pnl{font-family:var(--mono);font-size:12px;font-weight:600;}
  .op-pnl-pos{color:var(--green);}
  .op-pnl-neg{color:var(--red);}
  .op-key{font-family:var(--mono);font-size:8px;color:var(--text3);text-transform:uppercase;letter-spacing:0.08em;}
  .op-val{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--text0);}
  .op-val.red{color:var(--red);}
  .op-val.green{color:var(--green);}
  .op-tranche-pills{display:flex;gap:4px;flex-wrap:wrap;}
  .op-pill{font-family:var(--mono);font-size:8px;font-weight:600;padding:2px 6px;border-radius:2px;text-transform:uppercase;letter-spacing:0.06em;}
  .op-pill-active{background:var(--green-bg);color:var(--green);border:1px solid var(--green-dim);}
  .op-pill-sold{background:rgba(106,125,149,0.1);color:var(--text3);border:1px solid var(--border);text-decoration:line-through;}
  .op-pill-runner{background:rgba(155,127,232,0.12);color:var(--purple);border:1px solid var(--purple);}
  .op-expand{border-top:1px solid var(--border2);background:var(--bg3);padding:10px;display:flex;flex-direction:column;gap:10px;}
  .op-expand-label{font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.15em;color:var(--text3);text-transform:uppercase;margin-bottom:4px;}
  .op-btn-row{display:flex;gap:5px;flex-wrap:wrap;}
</style>
</head>
<body>

<div class="header">
  <div class="logo">CATALYST <span>/ COCKPIT</span></div>
  <div class="divider-v"></div>
  <div class="ticker-bar">
    <div class="ticker-input-wrap">
      <div class="ticker-prefix">$</div>
      <input id="tickerInput" type="text" placeholder="AAPL" maxlength="6" autocomplete="off"/>
    </div>
    <button class="btn btn-cyan" id="loadBtn">↓ LOAD SETUP</button>
    <button class="btn btn-ghost" id="resetBtn">RESET</button>
  </div>
  <div class="badge badge-paper">● PAPER</div>
  <div id="stateBadge" class="state-display state-idle">IDLE</div>
  <div class="live-price" id="livePriceDisplay" style="display:none">
    <span id="liveSymbol"></span><span id="livePrice"></span><span class="change" id="liveChange"></span>
  </div>
</div>

<div class="workspace">

  <div class="panel setup-panel">
    <div class="panel-header">
      <div class="panel-title">Setup Parameters</div>
      <div id="setupSymbol" style="font-family:var(--mono);font-size:11px;color:var(--text1);">—</div>
    </div>
    <div class="panel-body" id="setupBody">
      <div class="empty-state"><div class="empty-icon">⊡</div>Enter ticker and load setup</div>
    </div>
  </div>

  <div class="panel entry-panel">
    <div class="panel-header"><div class="panel-title">Trade Entry</div></div>
    <div class="panel-body" id="entryBody">
      <div style="color:var(--text3);font-family:var(--mono);font-size:11px;">Load a setup to enable entry actions.</div>
    </div>
  </div>

  <div class="panel protect-panel">
    <div class="panel-header">
      <div class="panel-title">Stop Protection</div>
      <div style="display:grid;grid-template-columns:60px 40px 64px 88px 88px 60px;align-items:center;gap:4px;">
        <span style="font-family:var(--mono);font-size:8px;font-weight:600;color:var(--text3);letter-spacing:0.1em;text-align:right;padding-right:4px;">STOPS</span>
        <button class="tranche-count-btn" id="stop1Btn" disabled onclick="selectStopMode(1)" style="height:24px;font-size:9px;">S1</button>
        <button class="tranche-count-btn" id="stop2Btn" disabled onclick="selectStopMode(2)" style="height:24px;font-size:9px;">S1·S2</button>
        <button class="tranche-count-btn active" id="stop3Btn" disabled onclick="selectStopMode(3)" style="height:24px;font-size:9px;">S1·S2·S3</button>
        <button id="stopOkBtn" disabled onclick="commitStopMode()" style="font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.1em;height:24px;border-radius:3px;cursor:pointer;border:1px solid var(--amber);background:var(--amber-bg);color:var(--amber);transition:all 0.15s;">EXECUTE</button>
        <div id="stopModeLabel" style="font-family:var(--mono);font-size:9px;color:var(--text3);"></div>
      </div>
    </div>
    <div style="padding:10px 14px;border-bottom:1px solid var(--border);">
      <div style="font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.15em;color:var(--text3);text-transform:uppercase;margin-bottom:8px;">Stop Plan <span id="stopModeHint" style="font-weight:400;color:var(--text3);letter-spacing:0;text-transform:none;">— enter trade first</span></div>
      <div id="stopPlanContent" style="width:100%;"></div>
    </div>
    <div class="panel-body" style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="btn btn-ghost" id="allBeBtn" disabled onclick="allToBE()">ALL → BE</button>
      <button class="btn btn-red" id="flattenBtn" disabled onclick="flattenPosition()">⬛ FLATTEN</button>
    </div>
  </div>

  <div class="panel manage-panel">
    <div class="panel-header">
      <div class="panel-title">Profit Taking</div>
      <div style="display:grid;grid-template-columns:60px 40px 64px 88px 88px 60px;align-items:center;gap:4px;">
        <span style="font-family:var(--mono);font-size:8px;font-weight:600;color:var(--text3);letter-spacing:0.1em;text-align:right;padding-right:4px;">TRANCHES</span>
        <button class="tranche-count-btn" id="tc1Btn" onclick="setTranchCount(1)" style="height:24px;font-size:9px;">P1</button>
        <button class="tranche-count-btn" id="tc2Btn" onclick="setTranchCount(2)" style="height:24px;font-size:9px;">P1·P2</button>
        <button class="tranche-count-btn active" id="tc3Btn" onclick="setTranchCount(3)" style="height:24px;font-size:9px;">P1·P2·P3</button>
        <button id="profitOkBtn" disabled onclick="commitProfitPlan()" style="font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.1em;height:24px;border-radius:3px;cursor:pointer;border:1px solid var(--amber);background:var(--amber-bg);color:var(--amber);transition:all 0.15s;">EXECUTE</button>
        <div id="positionSummaryHeader" style="font-family:var(--mono);font-size:10px;color:var(--text2);">No position</div>
      </div>
    </div>
    <div style="padding:10px 14px;border-bottom:1px solid var(--border);" id="exitPlanRow">
      <div style="font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.15em;color:var(--text3);text-transform:uppercase;margin-bottom:8px;">Exit Plan</div>
      <div id="exitPlanContent" style="width:100%;"></div>
    </div>
    <div style="flex:1;overflow:auto;padding:12px 14px;">
      <div class="section-label" id="trancheLabel" style="display:none">Exits</div>
      <div class="tranche-grid" id="trancheGrid" style="display:none"></div>
      <div class="pos-summary" id="posSummary" style="display:none"></div>
      <div class="section-label" id="ordersLabel" style="display:none">Orders</div>
      <table class="orders-table" id="ordersTable" style="display:none">
        <thead><tr><th>Order ID</th><th>Type</th><th>Qty</th><th>Price</th><th>Status</th><th>Tranche</th></tr></thead>
        <tbody id="ordersBody"></tbody>
      </table>
      <div id="manageEmpty" class="empty-state">
        <div class="empty-icon">◈</div>
        Set stop protection, then take profits manually
      </div>
    </div>
  </div>

  <div class="panel log-panel">
    <div class="panel-header">
      <div class="panel-title">Activity Log</div>
      <button class="btn btn-ghost" onclick="clearLog()" style="height:20px;padding:0 6px;font-size:8px;">CLR</button>
    </div>
    <div class="log-body" id="logBody">
      <div class="log-entry">
        <div class="log-time">--:--:--</div>
        <div class="log-msg"><span class="tag tag-sys">SYS</span> Cockpit initialized. Enter ticker to begin.</div>
      </div>
    </div>
  </div>

</div>

<script>
const MOCK={
  AAPL:{bid:213.85,ask:213.92,lod:210.40,sma10:211.20,sma50:198.40,sma200:195.20,sma200prev:194.80,atr:3.20,rvol:1.8,dtc:2.4},
  NVDA:{bid:875.20,ask:875.55,lod:862.10,sma10:868.50,sma50:780.00,sma200:720.00,sma200prev:722.50,atr:18.50,rvol:3.2,dtc:1.1},
  TSLA:{bid:248.10,ask:248.45,lod:242.30,sma10:245.80,sma50:220.50,sma200:210.30,sma200prev:209.80,atr:9.80,rvol:2.5,dtc:5.8},
  AMD:{bid:168.50,ask:168.70,lod:164.90,sma10:166.30,sma50:155.20,sma200:158.40,sma200prev:159.10,atr:5.40,rvol:1.1,dtc:3.2},
  MSFT:{bid:415.30,ask:415.55,lod:410.20,sma10:412.80,sma50:390.60,sma200:382.10,sma200prev:381.40,atr:6.10,rvol:2.1,dtc:0.9},
};

let state={
  phase:'idle',symbol:'',mock:null,setup:null,
  stopMode:0,tranches:[],orders:[],orderSeq:1,
  priceInterval:null,livePrice:null,
  accountEquity:100000,riskPct:1.0,
  posExpanded:null,manualBuffer:null,rootOrderId:null,
  positions:[],t1Pct:33,t2Pct:33,t3Pct:34,trancheCount:3,
  trancheModes:[
    {mode:'limit',trail:2.00,trailUnit:'$',target:'1R',manualPrice:null},
    {mode:'limit',trail:2.00,trailUnit:'$',target:'2R',manualPrice:null},
    {mode:'runner',trail:2.00,trailUnit:'$',target:'3R',manualPrice:null},
  ],
  stopModes:[{mode:'stop',pct:null},{mode:'stop',pct:null},{mode:'stop',pct:null}],
  stopRef:'lod',atrMult:1.0,manualStopPrice:null,
  stopArmed:false,profitArmed:false,pendingProfitIdx:0,
};

function selectStopMode(mode){
  // just highlights selection and previews — no orders placed
  state.stopMode=mode;
  ['stop1Btn','stop2Btn','stop3Btn'].forEach((id,i)=>{document.getElementById(id).classList.toggle('active',i+1===mode);});
  document.getElementById('stopModeLabel').textContent=`S${mode}`;
  // enable OK button
  const okBtn=document.getElementById('stopOkBtn');
  if(okBtn){okBtn.disabled=false;okBtn.style.opacity='1';okBtn.style.boxShadow='0 0 10px rgba(0,208,122,0.5)';}
  renderStopPlan();
  log(`Stop mode S${mode} selected — click OK to apply`,'sys');
}

function commitStopMode(){
  const mode=state.stopMode;
  if(!mode){log('Select a stop mode first','warn');return;}
  const activePhases=['trade_entered','protected','P1_done','P2_done','runner_only'];
  if(!activePhases.includes(state.phase)){log('Enter trade first before applying stops','warn');return;}
  const s=state.setup;
  const total=Math.round(s.shares);
  // filter STOP orders in-place to preserve shared reference with pos.orders
  const stopIdxs = state.orders.reduce((acc,o,i)=>{ if(o.type==='STOP') acc.push(i); return acc; },[]);
  for(let i=stopIdxs.length-1;i>=0;i--) state.orders.splice(stopIdxs[i],1);
  // stop price = finalStop (LoD/ATR/manual) — pct adjusts how tight above finalStop
  const baseStop=s.finalStop;
  const stopRange=s.entry-baseStop; // full risk range
  const stops=Array.from({length:mode},(_,i)=>{
    const sm=state.stopModes[i]||{mode:'stop',pct:null};
    const autoPct=i===mode-1?100-Math.floor(100/mode)*i:Math.floor(100/mode);
    const pct=sm.mode==='be'?0:(sm.pct!==null?sm.pct:autoPct);
    // price = entry minus (pct/100 * stopRange), so 33% = tight, 100% = full stop
    const price=sm.mode==='be'?s.entry:parseFloat((s.entry - stopRange * pct / 100).toFixed(2));
    const qty=i===mode-1?total-Math.floor(total/mode)*i:Math.floor(total/mode);
    const trancheIds=i===mode-1?state.tranches.slice(i).map(t=>t.id):[`T${i+1}`];
    return{price,qty,trancheIds,pct,label:`S${i+1}`};
  });
  stops.forEach((stop,i)=>{
    if(state.tranches[i])state.tranches[i].stop=stop.price;
    addOrder('STOP',stop.qty,stop.price,'ACTIVE',stop.label,stop.trancheIds,state.rootOrderId);
  });
  log(`✓ Stops applied — ${stops.map(s=>`${s.label} ${s.qty}sh @ ${fp(s.price)} (${s.pct.toFixed(2)}%)`).join(' · ')}`,'warn');
  ['p1Btn','p2Btn','p3Btn','beBtn','allBeBtn','refreshBtn','flattenBtn'].forEach(id=>{const el=document.getElementById(id);if(el&&el.style.display!=='none')el.disabled=false;});
  // dim OK after commit
  const okBtn=document.getElementById('stopOkBtn');
  if(okBtn){okBtn.style.borderColor='var(--amber)';okBtn.style.background='var(--amber-bg)';okBtn.style.color='var(--amber)';okBtn.style.boxShadow='none';}
  // enable profit OK
  const profitOk=document.getElementById('profitOkBtn');
  if(profitOk){profitOk.disabled=false;profitOk.style.opacity='1';profitOk.style.boxShadow='0 0 10px rgba(0,208,122,0.5)';}
  const posRecord=state.positions?.find(p=>p.symbol===state.symbol);
  if(posRecord)posRecord.stopMode=mode;
  setState(['trade_entered','protected'].includes(state.phase)?'protected':state.phase);
  renderOrders();renderStopPlan();renderOpenPositions();
  document.getElementById('ordersLabel').style.display='block';
  document.getElementById('ordersTable').style.display='table';
}

function commitProfitPlan(){
  const activePhases=['trade_entered','protected','P1_done','P2_done','runner_only'];
  if(!activePhases.includes(state.phase)){log('Enter trade and set stops first','warn');return;}

  // ensure rootOrderId is set
  if(!state.rootOrderId){
    const mkt=state.orders.find(o=>o.type==='MKT'&&!o.parentId);
    if(mkt)state.rootOrderId=mkt.id;
  }

  const s=state.setup;
  const r=s.perShareRisk;
  const entry=s.entry;
  const rPrices={'1R':entry+r,'2R':entry+2*r,'3R':entry+3*r};
  let executed=0;

  state.tranches.forEach((t,i)=>{
    if(t.status!=='active')return;
    const tm=state.trancheModes[i];
    if(tm.mode==='runner'){
      const trail=tm.trailUnit==='$'
        ?parseFloat((state.livePrice-tm.trail).toFixed(2))
        :parseFloat((state.livePrice*(1-tm.trail/100)).toFixed(2));
      t.runnerStop=trail;t.mode='runner';
      addOrder('TRAIL',t.qty,trail,'ACTIVE',t.id,[],state.rootOrderId);
      log(`P${i+1} RUNNER activated — trail stop @ ${fp(trail)}`,'exec');
    }else{
      const target=parseFloat((
        tm.target==='Manual'&&tm.manualPrice?tm.manualPrice
        :rPrices[tm.target]??(entry+(i+1)*r)
      ).toFixed(2));
      t.status='sold';
      adjustStopsForSoldTranche(t.id);
      addOrder('LMT',t.qty,target,'FILLED',t.id,[],state.rootOrderId);
      log(`P${i+1} executed: ${t.qty}sh @ ${fp(target)} (${tm.target}) → ${state.rootOrderId}`,'exec');
    }
    executed++;
  });

  if(executed===0){log('No active tranches to execute','warn');return;}

  // update phase
  const allSold=state.tranches.every(t=>t.status==='sold'||t.mode==='runner');
  const hasRunner=state.tranches.some(t=>t.mode==='runner');
  if(hasRunner)setState('runner_only');
  else setState('P'+Math.min(state.trancheCount,3)+'_done');

  // sync position record
  const posRec=state.positions?.find(p=>p.symbol===state.symbol);
  if(posRec){posRec.phase=state.phase;posRec.trancheModes=JSON.parse(JSON.stringify(state.trancheModes));}

  // dim CONFIRM button
  const okBtn=document.getElementById('profitOkBtn');
  if(okBtn){okBtn.style.borderColor='var(--amber)';okBtn.style.background='var(--amber-bg)';okBtn.style.color='var(--amber)';okBtn.style.boxShadow='none';}

  revealTrancheArea();
  document.getElementById('ordersLabel').style.display='block';
  document.getElementById('ordersTable').style.display='table';
  renderTranches();renderOrders();renderPosSummary();renderExitPlan();renderOpenPositions();
  log(`✓ Profit plan executed — ${executed} tranche(s) filled`,'exec');
}

const f2=v=>v?`$${v.toFixed(2)}`:'—';
const fp=v=>v?`${v.toFixed(2)}`:'—';
const fsh=v=>v?`${Math.round(v)} sh`:'—';
function now(){return new Date().toLocaleTimeString('en-US',{hour12:false});}

function log(msg,tag='info'){
  const lb=document.getElementById('logBody');
  const div=document.createElement('div');
  div.className='log-entry';
  div.innerHTML=`<div class="log-time">${now()}</div><div class="log-msg"><span class="tag tag-${tag}">${tag.toUpperCase()}</span> ${msg}</div>`;
  lb.prepend(div);
}
function clearLog(){document.getElementById('logBody').innerHTML='';log('Log cleared.','sys');}

function setState(phase){
  state.phase=phase;
  const pos=state.positions?.find(p=>p.symbol===state.symbol);
  if(pos)pos.phase=phase;
  const el=document.getElementById('stateBadge');
  const labels={idle:'IDLE',setup_loaded:'SETUP LOADED',trade_entered:'TRADE ENTERED',protected:'PROTECTED',P1_done:'P1 DONE',P2_done:'P2 DONE',runner_only:'RUNNER ONLY',closed:'CLOSED'};
  el.textContent=labels[phase]||phase.toUpperCase();
  el.className=`state-display state-${phase}`;
}

function nextOrderId(){return `ORD-${String(state.orderSeq++).padStart(4,'0')}`;}
function addOrder(type,qty,price,status,tranche,coveredTranches=[],parentId=null){
  const id=nextOrderId();
  state.orders.push({id,type,qty,origQty:qty,price,status,tranche,coveredTranches,parentId});
  return id;
}

function adjustStopsForSoldTranche(trancheId){
  const soldTranche=state.tranches?.find(t=>t.id===trancheId);
  if(!soldTranche||!state.orders?.length)return;
  state.orders.forEach(o=>{
    if(o.type!=='STOP'||o.status==='CANCELED')return;
    if(!o.coveredTranches.includes(trancheId))return;
    o.qty-=soldTranche.qty;
    o.coveredTranches=o.coveredTranches.filter(id=>id!==trancheId);
    if(o.qty<=0){o.qty=0;o.status='CANCELED';log(`Stop ${o.id} canceled — no shares remaining`,'sys');}
    else{o.status='MODIFIED';log(`Stop ${o.id} qty reduced to ${o.qty}sh (${trancheId} sold)`,'sys');}
  });
}

function loadSetup(){
  const raw=document.getElementById('tickerInput').value.trim().toUpperCase();
  const symbol=raw||'AAPL';
  document.getElementById('tickerInput').value=symbol;
  const m=MOCK[symbol]||MOCK.AAPL;
  const entry=parseFloat(((m.bid+m.ask)/2).toFixed(2));
  const finalStop=m.lod;
  const riskPct=state.riskPct/100;
  const dollarRisk=parseFloat((state.accountEquity*riskPct).toFixed(2));
  const perShareRisk=parseFloat((entry-finalStop).toFixed(2));
  const shares=Math.floor(dollarRisk/perShareRisk);
  const r1=perShareRisk;
  state.symbol=symbol;state.mock=m;state.livePrice=entry;
  state.setup={entry,finalStop,r1,r2:parseFloat((entry+2*r1).toFixed(2)),r3:parseFloat((entry+3*r1).toFixed(2)),shares,dollarRisk,perShareRisk,riskPct};
  state.stopMode=0;state.tranches=[];state.orders=[];
  state.rootOrderId=null;state.manualBuffer=null;state.manualStopPrice=null;
  state.stopModes.forEach(sm=>{sm.mode='stop';sm.pct=null;});
  ['stop1Btn','stop2Btn','stop3Btn','p1Btn','p2Btn','p3Btn','beBtn','allBeBtn','refreshBtn','flattenBtn'].forEach(id=>{const el=document.getElementById(id);if(el)el.disabled=true;});
  document.getElementById('trancheGrid').style.display='none';
  document.getElementById('posSummary').style.display='none';
  document.getElementById('ordersTable').style.display='none';
  document.getElementById('ordersLabel').style.display='none';
  document.getElementById('trancheLabel').style.display='none';
  document.getElementById('manageEmpty').style.display='block';
  document.getElementById('stopModeLabel').textContent='NOT SET';
  document.getElementById('stopModeHint').textContent='Enter trade first';
  renderSetupPanel();renderEntryPanel();renderExitPlan();renderStopPlan();startLivePrice();
  setState('setup_loaded');
  log(`Loaded mock setup for <strong>${symbol}</strong> — entry ${f2(entry)}, ${fsh(shares)} @ risk ${f2(dollarRisk)}`,'info');
}

function renderSetupPanel(){
  const s=state.setup;const m=state.mock;
  document.getElementById('setupSymbol').innerHTML=`<span class="ticker-symbol-large">${state.symbol}</span>`;
  document.getElementById('setupBody').innerHTML=`
    <div class="kv-group">
      <div class="kv-group-label">Quote</div>
      <div class="kv-row"><span class="kv-label">Bid</span><span class="kv-val">${fp(m.bid)}</span></div>
      <div class="kv-row"><span class="kv-label">Ask</span><span class="kv-val">${fp(m.ask)}</span></div>
      <div class="kv-row"><span class="kv-label">Suggested Entry</span><span class="kv-val cyan">${fp(s.entry)}</span></div>
    </div>
    <div class="kv-group">
      <div class="kv-group-label">Stop Levels</div>
      <div class="kv-row"><span class="kv-label">Low of Day</span><span class="kv-val">${fp(m.lod)}</span></div>
      <div class="kv-row"><span class="kv-label">ATR (14)</span><span class="kv-val amber">${fp(m.atr)}</span></div>
      <div class="kv-row"><span class="kv-label">Final Stop</span><span class="kv-val red" id="leftFinalStop">${fp(s.finalStop)}</span></div>
    </div>
    <div class="kv-group">
      <div class="kv-group-label">Risk Sizing</div>
      <div class="kv-row"><span class="kv-label">Account Equity</span><span class="kv-val">$100,000</span></div>
      <div class="kv-row">
        <span class="kv-label">Risk %</span>
        <input type="text" inputmode="decimal" id="riskPctInput" value="${state.riskPct}%"
          style="font-family:var(--mono);font-size:11px;font-weight:500;color:var(--amber);background:var(--bg3);border:1px solid var(--border2);width:50px;padding:0 5px;height:20px;outline:none;border-radius:2px;text-align:right;"
          onfocus="this.value=state.riskPct;this.style.borderColor='var(--amber)'"
          onblur="const v=parseFloat(this.value)||1;state.riskPct=v;this.value=v+'%';this.style.borderColor='var(--border2)';recomputeSetup()"
          oninput="const v=parseFloat(this.value);if(!isNaN(v)){state.riskPct=v;recomputeSetup();}" />
      </div>
      <div class="kv-row"><span class="kv-label">Dollar Risk</span><span class="kv-val red" id="leftDollarRisk">${f2(s.dollarRisk)}</span></div>
      <div class="kv-row"><span class="kv-label">Per-Share Risk</span><span class="kv-val" id="leftPerShareRisk">${f2(s.perShareRisk)}</span></div>
      <div class="kv-row"><span class="kv-label">Calc. Shares</span><span class="kv-val green" id="leftCalcShares">${Math.round(s.shares)} sh</span></div>
    </div>
    <div class="kv-group">
      <div class="kv-group-label">Reference</div>
      <div class="kv-row"><span class="kv-label">10 SMA</span><span class="kv-val">${fp(m.sma10)}</span></div>
      <div class="kv-row"><span class="kv-label">50 SMA</span><span class="kv-val">${fp(m.sma50)}</span></div>
      <div class="kv-row">
        <span class="kv-label">ATR Ext from 50MA</span>
        ${(() => {
          const ext = parseFloat(((s.entry - m.sma50) / m.atr).toFixed(2));
          const col = ext >= 8 ? 'var(--red)' : ext >= 4 ? 'var(--amber)' : 'var(--green)';
          return `<span class="kv-val" style="color:${col};">${ext}x</span>`;
        })()}
      </div>
      <div class="kv-row">
        <span class="kv-label">RVOL</span>
        <span class="kv-val" style="color:${m.rvol >= 2 ? 'var(--green)' : 'var(--red)'};">${m.rvol.toFixed(1)}x</span>
      </div>
      <div class="kv-row">
        <span class="kv-label">200 MA</span>
        <span class="kv-val" style="color:${m.sma200 < m.sma200prev ? 'var(--red)' : 'var(--green)'};">
          ${fp(m.sma200)} <span style="font-size:9px;">${m.sma200 < m.sma200prev ? '▼ DECLINING' : '▲ RISING'}</span>
        </span>
      </div>
      <div class="kv-row">
        <span class="kv-label">Ext from 10 MA</span>
        ${(() => {
          const ext = parseFloat(((s.entry - m.sma10) / m.sma10 * 100).toFixed(2));
          const col = ext > 10 ? 'var(--red)' : 'var(--green)';
          return `<span class="kv-val" style="color:${col};">${ext > 0 ? '+' : ''}${ext}%</span>`;
        })()}
      </div>
      <div class="kv-row">
        <span class="kv-label">Days to Cover</span>
        <span class="kv-val">${m.dtc.toFixed(1)} <span style="font-size:9px;color:var(--text2);">days</span></span>
      </div>
    </div>
    <div id="openPositionsSection"></div>`;
  renderOpenPositions();
}

function recomputeSetup(){
  if(!state.mock)return;
  const m=state.mock;
  const entry=state.setup?.entry??parseFloat(((m.bid+m.ask)/2).toFixed(2));
  state.setup={...state.setup,entry,finalStop:m.lod};
  const finalStop=parseFloat((getEffectiveStopPrice()??m.lod).toFixed(2));
  const riskPct=state.riskPct/100;
  const dollarRisk=parseFloat((state.accountEquity*riskPct).toFixed(2));
  const perShareRisk=parseFloat((entry-finalStop).toFixed(2));
  const shares=perShareRisk>0?Math.floor(dollarRisk/perShareRisk):0;
  const r1=perShareRisk;
  state.setup={entry,finalStop,r1,r2:parseFloat((entry+2*r1).toFixed(2)),r3:parseFloat((entry+3*r1).toFixed(2)),shares,dollarRisk,perShareRisk,riskPct};
  const upd=(id,val)=>{const el=document.getElementById(id);if(el)el.textContent=val;};
  upd('leftDollarRisk',f2(dollarRisk));upd('leftPerShareRisk',f2(perShareRisk));
  upd('leftCalcShares',`${Math.round(shares)} sh`);upd('leftFinalStop',fp(finalStop));
  upd('heroEntry',fp(entry));upd('heroShares',Math.round(shares));
}

function recomputeFromEntry(){
  if(!state.setup)return;
  const s=state.setup;
  const perShareRisk=parseFloat((s.entry-s.finalStop).toFixed(2));
  const shares=Math.floor((state.accountEquity*(state.riskPct/100))/perShareRisk);
  s.perShareRisk=perShareRisk;s.shares=shares;
  const upd=(id,val)=>{const el=document.getElementById(id);if(el)el.textContent=val;};
  upd('heroShares',Math.round(shares));upd('leftPerShareRisk',f2(perShareRisk));upd('leftCalcShares',`${Math.round(shares)} sh`);
  renderExitPlan();
}

function renderEntryPanel(){
  const s=state.setup;const m=state.mock;
  const total=Math.round(s.shares);
  const ref=state.stopRef;
  const stopPrice=getEffectiveStopPrice();
  let refInput='';
  if(ref==='atr'){refInput=`<div style="display:flex;align-items:center;gap:0;"><input type="text" inputmode="decimal" value="${state.atrMult}" style="font-family:var(--mono);font-size:11px;font-weight:600;color:var(--amber);background:var(--bg3);border:1px solid var(--border2);border-right:none;width:34px;height:22px;padding:0 4px;outline:none;border-radius:2px 0 0 2px;text-align:right;" onblur="state.atrMult=parseFloat(this.value)||1;recomputeSetup();renderEntryPanel();renderStopPlan();" onkeydown="if(event.key==='Enter')this.blur()"/><span style="font-family:var(--mono);font-size:10px;color:var(--text2);background:var(--bg3);border:1px solid var(--border2);border-left:none;height:22px;padding:0 5px;display:flex;align-items:center;border-radius:0 2px 2px 0;">× ATR</span></div>`;}
  else if(ref==='manual'){refInput=`<div style="display:flex;align-items:center;gap:0;"><span style="font-family:var(--mono);font-size:10px;color:var(--text2);background:var(--bg3);border:1px solid var(--border2);border-right:none;height:22px;padding:0 5px;display:flex;align-items:center;border-radius:2px 0 0 2px;">$</span><input type="text" inputmode="decimal" value="${state.manualStopPrice??''}" placeholder="${fp(s.finalStop)}" style="font-family:var(--mono);font-size:11px;font-weight:600;color:var(--red);background:var(--bg3);border:1px solid var(--border2);border-left:none;width:68px;height:22px;padding:0 4px;outline:none;border-radius:0 2px 2px 0;text-align:right;" onblur="state.manualStopPrice=parseFloat(this.value)||null;recomputeSetup();renderEntryPanel();renderStopPlan();" onkeydown="if(event.key==='Enter')this.blur()"/></div>`;}
  document.getElementById('entryBody').innerHTML=`
    <div style="display:flex;flex-direction:column;gap:12px;justify-content:center;height:100%;">
      <div style="display:flex;align-items:center;gap:28px;">
        <div style="font-family:var(--mono);font-size:9px;color:var(--text3);letter-spacing:0.14em;text-transform:uppercase;width:110px;">Entry Price</div>
        <div style="font-family:var(--mono);font-size:9px;color:var(--text3);letter-spacing:0.14em;text-transform:uppercase;width:90px;">Shares to Buy</div>
        <div style="width:1px;height:12px;"></div>
        <div style="font-family:var(--mono);font-size:9px;color:var(--text3);letter-spacing:0.14em;text-transform:uppercase;">Stop Reference</div>
      </div>
      <div style="display:flex;align-items:center;gap:28px;">
        <input id="heroEntry" type="text" inputmode="decimal" value="${fp(s.entry)}"
          style="font-family:var(--mono);font-size:26px;font-weight:600;color:var(--cyan);line-height:1;background:transparent;border:none;border-bottom:2px solid var(--cyan);width:110px;outline:none;padding:0 0 2px 0;"
          onblur="const v=parseFloat(this.value);if(!isNaN(v)&&v>0){state.setup.entry=v;recomputeFromEntry();}else{this.value=fp(state.setup.entry);}"
          oninput="const v=parseFloat(this.value);if(!isNaN(v)&&v>0){state.setup.entry=v;recomputeFromEntry();}"/>
        <div id="heroShares" style="font-family:var(--mono);font-size:26px;font-weight:600;color:var(--text0);line-height:1;width:90px;">${total}</div>
        <div style="width:1px;height:28px;background:var(--border2);"></div>
        <div style="display:flex;align-items:center;gap:6px;">
          <div style="display:flex;gap:2px;">
            <button class="tranche-count-btn ${ref==='lod'?'active':''}" onclick="setStopRef('lod')">LoD</button>
            <button class="tranche-count-btn ${ref==='atr'?'active':''}" onclick="setStopRef('atr')">ATR</button>
            <button class="tranche-count-btn ${ref==='manual'?'active':''}" onclick="setStopRef('manual')">Manual</button>
          </div>
          ${refInput}
          <span style="font-family:var(--mono);font-size:16px;font-weight:600;color:var(--red);">${fp(stopPrice)}</span>
        </div>
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-ghost" onclick="previewTrade()" id="previewBtn">PREVIEW</button>
        <button class="btn btn-cyan" onclick="enterTrade()" id="enterBtn">↗ ENTER TRADE</button>
      </div>
    </div>`;
}

function getEffectiveStopPrice(){
  const s=state.setup;const m=state.mock;
  if(!s)return null;
  if(state.stopRef==='atr')return parseFloat((s.entry-(m?.atr||0)*state.atrMult).toFixed(2));
  if(state.stopRef==='manual')return state.manualStopPrice??s.finalStop;
  return m?.lod??s.finalStop;
}

function renderExitPlan(){
  const el=document.getElementById('exitPlanContent');
  if(!el)return;
  const s=state.setup;
  const total=s?Math.round(s.shares):0;
  const count=state.trancheCount;
  let pcts;
  if(count===1)pcts=[100,0,0];
  else if(count===2)pcts=[state.t1Pct,100-state.t1Pct,0];
  else pcts=[state.t1Pct,state.t2Pct,state.t3Pct];
  const sharesArr=Array.from({length:count},(_,i)=>{
    if(i===count-1)return total-Array.from({length:i},(__,j)=>Math.floor(total*pcts[j]/100)).reduce((a,v)=>a+v,0);
    return Math.floor(total*pcts[i]/100);
  });
  const r=s?s.perShareRisk:0;
  const entry=s?s.entry:0;
  const rPrices={'1R':s?parseFloat((entry+r).toFixed(2)):null,'2R':s?parseFloat((entry+2*r).toFixed(2)):null,'3R':s?parseFloat((entry+3*r).toFixed(2)):null};

  const rows=Array.from({length:count},(_,i)=>{
    const tm=state.trancheModes[i];
    const isRunner=tm.mode==='runner';
    const col=isRunner?'var(--purple)':'var(--green)';
    const tgt=tm.target||'2R';
    const isManualTgt=tgt==='Manual';
    const targetPrice=isManualTgt?tm.manualPrice:rPrices[tgt];

    const trailCell=isRunner?`<div style="display:flex;align-items:center;gap:0;margin-left:10px;"><input class="trail-input" type="text" value="${tm.trail}" style="color:${col};" onblur="setTrailVal(${i},parseFloat(this.value)||2)" onkeydown="if(event.key==='Enter')this.blur()"/><button class="trail-unit-toggle" onclick="setTrailUnit(${i})">${tm.trailUnit}</button></div>`:'';

    const pctCell=count===1?`<span style="font-family:var(--mono);font-size:12px;font-weight:600;color:${col};display:inline-block;width:52px;text-align:right;">100%</span>`:`<div style="display:flex;align-items:center;gap:0;"><input type="text" inputmode="decimal" value="${pcts[i]}" style="font-family:var(--mono);font-size:12px;font-weight:600;color:${col};background:var(--bg3);border:1px solid var(--border2);border-right:none;width:34px;height:22px;padding:0 4px;outline:none;border-radius:2px 0 0 2px;text-align:right;" onblur="updateSplit(${i},parseFloat(this.value)||${pcts[i]})" onkeydown="if(event.key==='Enter')this.blur()" onfocus="this.style.borderColor='${col}'"/><span style="font-family:var(--mono);font-size:10px;color:var(--text2);background:var(--bg3);border:1px solid var(--border2);border-left:none;height:22px;padding:0 4px;display:flex;align-items:center;border-radius:0 2px 2px 0;">%</span></div>`;

    const rToggle=(()=>{
      if(isRunner)return'';
      const tgtCol=tgt==='Manual'?'var(--amber)':'var(--green)';
      const opts=['1R','2R','3R','Manual'];
      const next=opts[(opts.indexOf(tgt)+1)%opts.length];
      return`<button class="tranche-count-btn active" style="font-size:10px;padding:0 8px;height:22px;color:${tgtCol};border-color:${tgtCol};background:transparent;" onclick="setTrancheTarget(${i},'${next}')">${tgt}</button>`;
    })();

    const manualInput=isManualTgt?`<div style="display:flex;align-items:center;gap:0;"><span style="font-family:var(--mono);font-size:9px;color:var(--text2);background:var(--bg3);border:1px solid var(--border2);border-right:none;height:22px;padding:0 4px;display:flex;align-items:center;border-radius:2px 0 0 2px;">$</span><input type="text" inputmode="decimal" value="${tm.manualPrice??''}" placeholder="price" style="font-family:var(--mono);font-size:11px;font-weight:600;color:var(--amber);background:var(--bg3);border:1px solid var(--border2);border-left:none;width:62px;height:22px;padding:0 4px;outline:none;border-radius:0 2px 2px 0;text-align:right;" onblur="setTrancheManualPrice(${i},parseFloat(this.value))" onkeydown="if(event.key==='Enter')this.blur()"/></div>`:'';

    const priceCol=isRunner?(()=>{
      const trailStop=tm.trailUnit==='$'?parseFloat(((state.livePrice||0)-tm.trail).toFixed(2)):parseFloat(((state.livePrice||0)*(1-tm.trail/100)).toFixed(2));
      return`<span style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--purple);display:inline-block;width:64px;text-align:right;">${trailStop>0?fp(trailStop):'—'}</span>`;
    })():isManualTgt?`<div style="width:64px;">${manualInput}</div>`:`<span style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--green);display:inline-block;width:64px;text-align:right;">${targetPrice?fp(targetPrice):'—'}</span>`;

    const tranche=state.tranches[i];
    const isDone=tranche&&tranche.status==='sold';
    return`<div style="display:flex;align-items:center;padding:6px 10px;background:var(--bg2);border:1px solid ${isDone?'var(--border)':'var(--border2)'};border-radius:3px;margin-bottom:4px;opacity:${isDone?'0.5':'1'};">
      <span style="font-family:var(--mono);font-size:10px;font-weight:600;color:var(--text2);width:24px;flex-shrink:0;">P${i+1}</span>
      <div style="width:60px;flex-shrink:0;"><button class="mode-toggle ${isRunner?'runner':'limit'}" onclick="toggleTrancheMode(${i})" style="width:56px;text-align:center;">${isRunner?'RUNNER':'LIMIT'}</button></div>
      <div style="width:62px;flex-shrink:0;display:flex;justify-content:flex-end;">${pctCell}</div>
      <div style="width:72px;flex-shrink:0;display:flex;justify-content:flex-end;">${priceCol}</div>
      <div style="width:52px;flex-shrink:0;text-align:right;font-family:var(--mono);font-size:10px;color:var(--text1);">${total?sharesArr[i]+' sh':'—'}</div>
      <div style="width:62px;flex-shrink:0;display:flex;justify-content:flex-end;">${isRunner?trailCell:rToggle}</div>
      ${isDone?`<span style="font-family:var(--mono);font-size:9px;color:var(--green);margin-left:8px;">✓</span>`:''}
    </div>`;
  }).join('');
  el.innerHTML=`<div style="width:100%;">${rows}</div>`;
}

function setTrancheTarget(idx,tgt){state.trancheModes[idx].target=tgt;if(tgt!=='Manual')state.trancheModes[idx].manualPrice=null;renderExitPlan();}
function setTrancheManualPrice(idx,val){if(!isNaN(val)&&val>0)state.trancheModes[idx].manualPrice=val;}
function setTranchCount(n){
  state.trancheCount=n;
  if(n<3)state.trancheModes[n-1].mode='runner';
  if(n===1){state.t1Pct=100;}
  if(n===2){state.t1Pct=50;state.t2Pct=50;}
  if(n===3){state.t1Pct=33;state.t2Pct=33;state.t3Pct=34;}
  ['tc1Btn','tc2Btn','tc3Btn'].forEach((id,i)=>document.getElementById(id).classList.toggle('active',i+1===n));
  renderExitPlan();
}
function toggleTrancheMode(idx){state.trancheModes[idx].mode=state.trancheModes[idx].mode==='limit'?'runner':'limit';renderExitPlan();}
function setTrailUnit(idx){state.trancheModes[idx].trailUnit=state.trancheModes[idx].trailUnit==='$'?'%':'$';renderExitPlan();}
function setTrailVal(idx,val){state.trancheModes[idx].trail=val;}
function updateSplit(idx,val){
  if(state.trancheCount===1)return;
  val=Math.max(1,Math.min(98,Math.round(val)));
  const pcts=[state.t1Pct,state.t2Pct,state.t3Pct];
  pcts[idx]=val;
  const count=state.trancheCount;
  const others=Array.from({length:count},(_,i)=>i).filter(i=>i!==idx);
  const remaining=100-val;
  const sumOthers=others.reduce((a,i)=>a+pcts[i],0);
  others.forEach((i,j)=>{pcts[i]=j===others.length-1?remaining-others.slice(0,j).reduce((a,k)=>a+pcts[k],0):Math.round(remaining*pcts[i]/(sumOthers||1));});
  [state.t1Pct,state.t2Pct,state.t3Pct]=pcts;
  renderExitPlan();
}

function renderStopPlan(){
  const el=document.getElementById('stopPlanContent');
  if(!el)return;
  const s=state.setup;
  if(!s){el.innerHTML='';return;}
  const mode=state.stopMode||3;
  const total=Math.round(s.shares);
  const stopRange=s.entry-s.finalStop; // full risk range entry→finalStop
  const stops=Array.from({length:mode},(_,i)=>{
    const sm=state.stopModes[i]||{mode:'stop',pct:null};
    const autoPct=i===mode-1?parseFloat((100-Math.floor(100/mode)*i).toFixed(2)):parseFloat((100/mode).toFixed(2));
    const pct=sm.mode==='be'?0:(sm.pct!==null?sm.pct:autoPct);
    const price=sm.mode==='be'?s.entry:parseFloat((s.entry - stopRange * pct / 100).toFixed(2));
    const qty=i===mode-1?total-Math.floor(total/mode)*i:Math.floor(total/mode);
    return{label:`S${i+1}`,pct,price,qty};
  });
  const applied=state.stopMode>0&&state.tranches.length>0;
  el.innerHTML=stops.map((stop,i)=>{
    const sm=state.stopModes[i]||{mode:'stop',pct:null};
    const isBE=sm.mode==='be';
    const displayPct=isBE?'0.00':stop.pct.toFixed(2);
    const displayPrice=isBE?s.entry:stop.price;
    const col=isBE?'var(--cyan)':'var(--red)';
    const activeOrder=applied&&state.orders?.find(o=>o.type==='STOP'&&o.status!=='CANCELED'&&(o.coveredTranches?.includes(`T${i+1}`)||Math.abs(o.price-stop.price)<0.05));
    const statusCol=!applied?'var(--text3)':activeOrder?'var(--green)':'var(--text3)';
    const statusLabel=!applied?'PREVIEW':activeOrder?'ACTIVE':'PREVIEW';
    return`<div style="display:flex;align-items:center;gap:10px;padding:6px 10px;background:var(--bg2);border:1px solid var(--border2);border-radius:3px;margin-bottom:4px;">
      <span style="font-family:var(--mono);font-size:10px;font-weight:600;color:var(--text2);width:22px;">${stop.label}</span>
      <button class="mode-toggle ${isBE?'runner':'limit'}" style="width:42px;text-align:center;font-size:8px;" onclick="toggleStopMode(${i})">${isBE?'BE':'STOP'}</button>
      <div style="display:flex;align-items:center;gap:0;">
        <input type="text" inputmode="decimal" value="${displayPct}" ${isBE?'disabled':''}
          style="font-family:var(--mono);font-size:12px;font-weight:600;color:${col};background:var(--bg3);border:1px solid var(--border2);border-right:none;width:48px;height:22px;padding:0 4px;outline:none;border-radius:2px 0 0 2px;text-align:right;${isBE?'opacity:0.5;':''}"
          onblur="setStopPct(${i},parseFloat(this.value))"
          onkeydown="if(event.key==='Enter')this.blur()"/>
        <span style="font-family:var(--mono);font-size:10px;color:var(--text2);background:var(--bg3);border:1px solid var(--border2);border-left:none;height:22px;padding:0 4px;display:flex;align-items:center;border-radius:0 2px 2px 0;">%</span>
      </div>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text3);">${fp(displayPrice)}</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text1);">${stop.qty} sh</span>
      <span style="font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.1em;color:${statusCol};margin-left:auto;">${statusLabel}</span>
    </div>`;
  }).join('');
}

function setStopRef(ref){
  state.stopRef=ref;state.stopModes.forEach(sm=>sm.pct=null);
  if(ref!=='manual')state.manualStopPrice=null;
  recomputeSetup();renderEntryPanel();renderStopPlan();
  const refLabel=ref==='atr'?`ATR ×${state.atrMult}`:ref==='manual'?'Manual':`LoD (${fp(state.mock?.lod)})`;
  if(state.setup)log(`Stop reference → ${refLabel}`,'sys');
}
function toggleStopMode(idx){state.stopModes[idx].mode=state.stopModes[idx].mode==='stop'?'be':'stop';renderStopPlan();}
function setStopPct(idx,val){if(!isNaN(val)&&val>0){state.stopModes[idx].pct=parseFloat(val.toFixed(2));renderStopPlan();}}

function renderOpenPositions(){
  const el=document.getElementById('openPositionsSection');
  if(!el)return;
  const activePhases=['trade_entered','protected','P1_done','P2_done','runner_only'];
  const openPositions=state.positions.filter(p=>activePhases.includes(p.phase));
  if(!openPositions.length){el.innerHTML='';return;}

  const cards=openPositions.map(pos=>{
    const s=pos.setup;
    const livePrice=pos.livePrice||s.entry;
    const activeShares=pos.tranches.filter(t=>t.status==='active').reduce((a,t)=>a+t.qty,0);
    const pnl=parseFloat(((livePrice-s.entry)*activeShares).toFixed(2));
    const pnlSign=pnl>=0?'+':'';
    const pnlClass=pnl>=0?'op-pnl-pos':'op-pnl-neg';
    const isActive=pos.symbol===state.symbol;
    const stopEnabled=pos.stopMode>0;
    const profitEnabled=pos.symbol===state.symbol?state.profitArmed:false;

    return`<div class="op-card" style="cursor:pointer;${isActive?'border-color:var(--cyan);border-left:3px solid var(--cyan);':''}" onclick="selectPosition('${pos.symbol}');renderOpenPositions();">
      <div class="op-card-header">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span class="op-symbol">${pos.symbol}</span>
          <span class="op-pnl ${pnlClass}">${pnlSign}${f2(pnl)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="flex-shrink:0;">
            <span class="op-key">ENTRY</span><br>
            <span class="op-val">${fp(s.entry)}</span>
          </div>
          <div style="flex-shrink:0;">
            <span class="op-key">LIVE</span><br>
            <span class="op-val">${fp(livePrice)}</span>
          </div>
          <div style="margin-left:auto;display:flex;gap:4px;align-items:center;">
            <span style="font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.08em;padding:2px 6px;border-radius:2px;${stopEnabled?'background:rgba(0,208,122,0.12);color:var(--green);border:1px solid var(--green-dim);':'background:rgba(255,64,96,0.08);color:var(--red);border:1px solid var(--red-dim);'}">STOP ${stopEnabled?'SET':'—'}</span>
            <span style="font-family:var(--mono);font-size:8px;font-weight:600;letter-spacing:0.08em;padding:2px 6px;border-radius:2px;${profitEnabled?'background:rgba(0,200,212,0.1);color:var(--cyan);border:1px solid rgba(0,200,212,0.3);':'background:rgba(106,125,149,0.1);color:var(--text3);border:1px solid var(--border);'}">PROFIT ${profitEnabled?'ON':'—'}</span>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');
  el.innerHTML=`<div class="op-section-label">Open Positions <span style="color:var(--text3);font-weight:400;">(${openPositions.length})</span><span style="color:var(--green);font-size:8px;">● LIVE</span></div>${cards}`;
}

function selectPosition(symbol){
  const pos=state.positions?.find(p=>p.symbol===symbol);
  if(!pos)return;
  state.symbol=pos.symbol;state.mock=pos.mock;state.setup=pos.setup;
  state.tranches=pos.tranches;state.orders=pos.orders;state.phase=pos.phase;
  state.stopMode=pos.stopMode;state.rootOrderId=pos.rootOrderId;state.livePrice=pos.livePrice;
  if(pos.trancheCount)state.trancheCount=pos.trancheCount;
  if(pos.trancheModes)state.trancheModes=JSON.parse(JSON.stringify(pos.trancheModes));
  // refresh all main panels to reflect this position
  renderSetupPanel();
  renderEntryPanel();
  renderStopPlan();
  renderExitPlan();
  renderTranches();
  renderOrders();
  renderPosSummary();
  setState(pos.phase);
  // enable stop buttons if trade is active
  const activePhases=['trade_entered','protected','P1_done','P2_done','runner_only'];
  if(activePhases.includes(pos.phase)){
    ['stop1Btn','stop2Btn','stop3Btn'].forEach(id=>{const el=document.getElementById(id);if(el)el.disabled=false;});
    ['allBeBtn','flattenBtn'].forEach(id=>{const el=document.getElementById(id);if(el)el.disabled=false;});
    const stopOk=document.getElementById('stopOkBtn');
    if(stopOk){stopOk.disabled=false;stopOk.style.borderColor='var(--green)';stopOk.style.background='var(--green)';stopOk.style.color='#000';stopOk.style.boxShadow='0 0 10px rgba(0,208,122,0.5)';}
    const profitOk=document.getElementById('profitOkBtn');
    if(profitOk){profitOk.disabled=false;profitOk.style.borderColor='var(--green)';profitOk.style.background='var(--green)';profitOk.style.color='#000';profitOk.style.boxShadow='0 0 10px rgba(0,208,122,0.5)';}
  }
  log(`Switched to position: <strong>${symbol}</strong>`,'sys');
}

function togglePosExpand(symbol){
  // selecting a card also makes it the active position
  selectPosition(symbol);
  state.posExpanded=state.posExpanded===symbol?null:symbol;
  renderOpenPositions();
}

function startLivePrice(){
  if(state.priceInterval)clearInterval(state.priceInterval);
  const display=document.getElementById('livePriceDisplay');
  display.style.display='flex';
  document.getElementById('liveSymbol').textContent=state.symbol+'  ';
  tickPrice();
  state.priceInterval=setInterval(tickPrice,2000);
}

function tickPrice(){
  const jitter=(Math.random()-0.5)*0.3;
  state.livePrice=parseFloat((state.livePrice+jitter).toFixed(2));
  const base=state.setup.entry;
  const delta=state.livePrice-base;
  const pct=((delta/base)*100).toFixed(2);
  const dir=delta>=0?'+':'';
  document.getElementById('livePrice').textContent=fp(state.livePrice);
  document.getElementById('liveChange').className=`change ${delta>=0?'up':'dn'}`;
  document.getElementById('liveChange').textContent=`${dir}${fp(delta)} (${dir}${pct}%)`;
  state.positions.forEach(pos=>{pos.livePrice=parseFloat(((pos.livePrice||pos.setup.entry)+(Math.random()-0.5)*0.3).toFixed(2));});
  renderOpenPositions();
}

function previewTrade(){
  const s=state.setup;
  log(`Preview: ${state.symbol} — Buy ${Math.round(s.shares)} sh @ ${fp(s.entry)} — Stop: ${fp(s.finalStop)} — Risk: ${f2(s.dollarRisk)}`,'info');
}

function enterTrade(){
  if(state.phase!=='setup_loaded')return;
  const s=state.setup;
  const count=state.trancheCount;
  const total=s.shares;
  const pcts=[state.t1Pct,state.t2Pct,state.t3Pct];
  const qtys=[];
  for(let i=0;i<count;i++){qtys.push(i===count-1?total-qtys.reduce((a,v)=>a+v,0):Math.floor(total*pcts[i]/100));}
  state.tranches=qtys.map((qty,i)=>({id:`T${i+1}`,qty,stop:s.finalStop,target:null,status:'active',mode:state.trancheModes[i].mode,trail:state.trancheModes[i].trail,trailUnit:state.trancheModes[i].trailUnit,label:`Tranche ${i+1} · P${i+1}`}));
  state.rootOrderId=addOrder('MKT',s.shares,s.entry,'FILLED',state.symbol);
  const posData={symbol:state.symbol,setup:{...s},tranches:state.tranches,orders:state.orders,phase:'trade_entered',stopMode:0,rootOrderId:state.rootOrderId,livePrice:state.livePrice,mock:state.mock,trancheCount:state.trancheCount,trancheModes:JSON.parse(JSON.stringify(state.trancheModes))};
  const existingPos=state.positions?.find(p=>p.symbol===state.symbol);
  if(existingPos){Object.assign(existingPos,posData);}
  else{state.positions.push(posData);}
  setState('trade_entered');
  enableStopButtons();
  document.getElementById('stopModeHint').textContent='Choose stop mode ↑';
  // show orders area immediately on trade entry
  document.getElementById('manageEmpty').style.display='none';
  document.getElementById('ordersLabel').style.display='block';
  document.getElementById('ordersTable').style.display='table';
  document.getElementById('trancheLabel').style.display='block';
  document.getElementById('trancheGrid').style.display='grid';
  document.getElementById('posSummary').style.display='flex';
  log(`Trade entered: Buy ${s.shares} sh ${state.symbol} @ ${fp(s.entry)} (MKT simulated)`,'exec');
  log(`Tranches: ${qtys.map((q,i)=>`T${i+1}=${q}sh`).join(' · ')}`,'sys');
  renderOpenPositions();
}

function enableStopButtons(){
  ['stop1Btn','stop2Btn','stop3Btn'].forEach(id=>{document.getElementById(id).disabled=false;});
  // pre-select S3 as default and enable OK
  selectStopMode(state.stopMode||3);
  const okBtn=document.getElementById('stopOkBtn');
  if(okBtn){okBtn.disabled=false;okBtn.style.opacity='1';okBtn.style.boxShadow='0 0 10px rgba(0,208,122,0.5)';}
  document.getElementById('stopModeHint').textContent='';
  renderStopPlan();
}

function revealTrancheArea(){
  document.getElementById('manageEmpty').style.display='none';
  document.getElementById('trancheLabel').style.display='block';
  document.getElementById('trancheGrid').style.display='grid';
  document.getElementById('posSummary').style.display='flex';
  document.getElementById('ordersLabel').style.display='block';
  document.getElementById('ordersTable').style.display='table';
}

function execExit(idx){
  if(!state.profitArmed){
    log(`Confirm profit plan first (click OK in Profit Taking)`,'warn');
    const btn=document.getElementById('profitOkBtn');
    if(btn){btn.classList.add('flash');setTimeout(()=>btn.classList.remove('flash'),400);}
    return;
  }
  const t=state.tranches[idx];
  if(!t||t.status!=='active')return;
  const pBtnId=['p1Btn','p2Btn','p3Btn'][idx];
  const tm=state.trancheModes[idx];
  if(tm.mode==='runner'){
    const trail=tm.trailUnit==='$'?parseFloat((state.livePrice-tm.trail).toFixed(2)):parseFloat((state.livePrice*(1-tm.trail/100)).toFixed(2));
    t.runnerStop=trail;t.mode='runner';
    log(`Runner activated: P${idx+1} ${t.qty}sh — trail stop @ ${fp(trail)}`,'exec');
    setState('runner_only');
  }else{
    const r=state.setup.perShareRisk;const entry=state.setup.entry;
    const rPrices={'1R':entry+r,'2R':entry+2*r,'3R':entry+3*r};
    const target=parseFloat((tm.target==='Manual'&&tm.manualPrice?tm.manualPrice:rPrices[tm.target]??(entry+(idx+1)*r)).toFixed(2));
    t.status='sold';adjustStopsForSoldTranche(t.id);
    // ensure rootOrderId is set — fallback to first MKT order if missing
    if(!state.rootOrderId){
      const mkt=state.orders.find(o=>o.type==='MKT'&&!o.parentId);
      if(mkt)state.rootOrderId=mkt.id;
    }
    const newOrderId=addOrder('LMT',t.qty,target,'FILLED',t.id,[],state.rootOrderId);
    log(`P${idx+1} executed: Sold ${t.qty}sh @ ${fp(target)} — Order ${newOrderId} → parent ${state.rootOrderId}`,'exec');
    const phases=['P1_done','P2_done','P3_done'];
    setState(phases[idx]||'P1_done');
  }
  const pBtn=document.getElementById(pBtnId);if(pBtn)pBtn.disabled=true;
  // sync position record phase
  const posRec=state.positions?.find(p=>p.symbol===state.symbol);
  if(posRec){posRec.phase=state.phase;posRec.trancheModes=JSON.parse(JSON.stringify(state.trancheModes));}
  revealTrancheArea();
  document.getElementById('ordersLabel').style.display='block';
  document.getElementById('ordersTable').style.display='table';
  renderTranches();renderOrders();renderPosSummary();renderOpenPositions();renderExitPlan();
}

function execP1(){execExit(0);}
function execP2(){execExit(1);}
function execRunner(){execExit(2);}

function moveToBE(){
  const activePhases=['trade_entered','protected','P1_done','P2_done','runner_only'];
  if(!activePhases.includes(state.phase))return;
  state.tranches.forEach(t=>{if(t.status==='active')t.stop=state.setup.entry;});
  state.orders.forEach(o=>{if(o.type==='STOP'&&o.status==='ACTIVE')o.price=state.setup.entry;});
  log(`Stops moved to breakeven: ${fp(state.setup.entry)}`,'warn');
  renderTranches();renderOrders();renderStopPlan();renderOpenPositions();
}

function allToBE(){
  const activePhases=['trade_entered','protected','P1_done','P2_done','runner_only'];
  if(!activePhases.includes(state.phase))return;
  state.tranches.forEach(t=>{if(t.status==='active')t.stop=state.setup.entry;});
  state.orders.forEach(o=>{if(o.type==='STOP'&&(o.status==='ACTIVE'||o.status==='MODIFIED'))o.price=state.setup.entry;});
  state.stopModes.forEach(sm=>{sm.mode='be';});
  log(`All stops → breakeven: ${fp(state.setup.entry)}`,'warn');
  renderTranches();renderOrders();renderStopPlan();renderOpenPositions();
}

function refreshOrders(){
  log(`Orders refreshed (mock state synced)`,'sys');
  renderOrders();renderTranches();renderPosSummary();
  const btn=document.getElementById('refreshBtn');
  btn.classList.add('flash');setTimeout(()=>btn.classList.remove('flash'),400);
}

function flattenPosition(){
  state.tranches.forEach(t=>{if(t.status==='active'){addOrder('MKT',t.qty,state.livePrice,'FILLED',t.id,[],state.rootOrderId);t.status='sold';}});
  state.orders.forEach(o=>{if(o.status==='ACTIVE')o.status='CANCELED';});
  setState('closed');
  log(`⬛ POSITION FLATTENED — all tranches closed @ market`,'close');
  state.positions=state.positions.filter(p=>p.symbol!==state.symbol);
  revealTrancheArea();renderOpenPositions();
  ['p1Btn','p2Btn','p3Btn','beBtn','allBeBtn','refreshBtn','flattenBtn','stop1Btn','stop2Btn','stop3Btn'].forEach(id=>{const el=document.getElementById(id);if(el)el.disabled=true;});
  renderTranches();renderOrders();renderPosSummary();
}

function renderTranches(){
  const grid=document.getElementById('trancheGrid');
  const s=state.setup;
  const statusClass={active:'active',sold:'sold',canceled:'canceled'};
  const statusLabel={active:'ACTIVE',sold:'SOLD',canceled:'CANCELED'};
  const visible=state.tranches.filter(t=>t.status==='sold'||t.status==='canceled'||(t.id==='T3'&&state.phase==='runner_only'));
  grid.innerHTML=visible.map(t=>{
    const sc=statusClass[t.status]||'active';
    const sl=statusLabel[t.status]||t.status.toUpperCase();
    const pnl=t.status==='sold'?parseFloat(((t.target||state.livePrice)-s.entry)*t.qty):null;
    return`<div class="tranche-card ${sc}">
      <div class="tranche-label">${t.id} · ${t.label.split('·')[1].trim()}</div>
      <div class="tranche-qty">${t.qty} <span style="font-size:10px;color:var(--text2)">sh</span></div>
      <div class="tranche-stop">↓ STOP  ${fp(t.stop)}</div>
      <div class="tranche-target">${t.target?`↑ TGT  ${fp(t.target)}`:'↑ RUNNER'}</div>
      ${pnl!==null?`<div style="font-family:var(--mono);font-size:10px;margin-top:4px;color:${pnl>=0?'var(--green)':'var(--red)'}">${pnl>=0?'+':''}${f2(pnl)}</div>`:''}
      <div class="tranche-status status-${sc}"><span class="status-dot"></span>${sl}</div>
    </div>`;
  }).join('');
}

function renderPosSummary(){
  const s=state.setup;
  const activeQty=state.tranches.filter(t=>t.status==='active').reduce((a,t)=>a+t.qty,0);
  const soldQty=state.tranches.filter(t=>t.status==='sold').reduce((a,t)=>a+t.qty,0);
  const notional=parseFloat((activeQty*s.entry).toFixed(2));
  document.getElementById('positionSummaryHeader').textContent=`${activeQty}sh active / ${soldQty}sh sold`;
  document.getElementById('posSummary').innerHTML=`
    <div class="pos-item"><div class="pos-item-label">Total Shares</div><div class="pos-item-val">${s.shares}</div></div>
    <div class="pos-item"><div class="pos-item-label">Active</div><div class="pos-item-val green">${activeQty} sh</div></div>
    <div class="pos-item"><div class="pos-item-label">Sold</div><div class="pos-item-val">${soldQty} sh</div></div>
    <div class="pos-item"><div class="pos-item-label">Entry</div><div class="pos-item-val">${fp(s.entry)}</div></div>
    <div class="pos-item"><div class="pos-item-label">Notional</div><div class="pos-item-val">${f2(notional)}</div></div>`;
}

function renderOrders(){
  const tb=document.getElementById('ordersTable');
  const ob=document.getElementById('ordersBody');
  const ol=document.getElementById('ordersLabel');
  tb.style.display='table';ol.style.display='block';
  const roots=state.orders.filter(o=>!o.parentId);
  const childrenOf=id=>state.orders.filter(o=>o.parentId===id);
  const typeColor={STOP:'var(--red)',LMT:'var(--cyan)',MKT:'var(--amber)',TRAIL:'var(--purple)'};
  let rows='';
  roots.forEach(root=>{
    const children=childrenOf(root.id);
    rows+=`<tr style="border-bottom:${children.length>0?'none':'1px solid var(--border)'}">
      <td style="font-family:var(--mono);color:var(--text1);font-weight:600;white-space:nowrap;">${root.id}</td>
      <td style="color:${typeColor[root.type]||'var(--text1)'};">${root.type}</td>
      <td style="font-family:var(--mono)">${root.qty}</td>
      <td style="font-family:var(--mono)">${fp(root.price)}</td>
      <td class="order-status-${root.status}">${root.status}</td>
      <td style="color:var(--text2)">${root.tranche}</td>
    </tr>`;
    children.forEach((child,idx)=>{
      const isLast=idx===children.length-1;
      rows+=`<tr style="background:rgba(0,0,0,0.15);border-bottom:${isLast?'2px solid var(--border2)':'1px solid rgba(30,42,58,0.4)'}">
        <td style="font-family:var(--mono);white-space:nowrap;padding-left:6px;"><span style="color:var(--text3);font-size:11px;margin-right:3px;letter-spacing:-1px;">${isLast?'└─':'├─'}</span><span style="color:var(--text2)">${child.id}</span></td>
        <td style="color:${typeColor[child.type]||'var(--text1)'};">${child.type}</td>
        <td style="font-family:var(--mono);color:${child.qty<child.origQty?'var(--amber)':'inherit'}">${child.qty}${child.qty<child.origQty?` <span style="color:var(--text3);font-size:9px;">(${child.origQty})</span>`:''}</td>
        <td style="font-family:var(--mono)">${fp(child.price)}</td>
        <td class="order-status-${child.status}">${child.status}</td>
        <td style="color:var(--text2)">${child.tranche}</td>
      </tr>`;
    });
  });
  ob.innerHTML=rows||`<tr><td colspan="6" style="color:var(--text3);font-family:var(--mono);font-size:10px;padding:8px;">No orders yet</td></tr>`;
  // scroll orders into view
  const ordersEl=document.getElementById('ordersTable');
  if(ordersEl)setTimeout(()=>ordersEl.scrollIntoView({behavior:'smooth',block:'nearest'}),100);
}

document.getElementById('tickerInput').addEventListener('keydown',e=>{if(e.key==='Enter')loadSetup();});
document.getElementById('loadBtn').addEventListener('click',loadSetup);
document.getElementById('resetBtn').addEventListener('click',()=>{
  if(state.priceInterval)clearInterval(state.priceInterval);
  state.phase='idle';state.symbol='';state.mock=null;state.setup=null;
  state.stopMode=0;state.tranches=[];state.orders=[];state.orderSeq=1;
  state.priceInterval=null;state.livePrice=null;state.rootOrderId=null;
  state.manualBuffer=null;state.manualStopPrice=null;state.posExpanded=null;
  state.positions=[];state.stopArmed=false;state.profitArmed=false;
  state.stopModes.forEach(sm=>{sm.mode='stop';sm.pct=null;});
  ['stopOkBtn','profitOkBtn'].forEach(id=>{const btn=document.getElementById(id);if(!btn)return;btn.disabled=true;btn.style.opacity='0.35';});
  document.getElementById('tickerInput').value='';
  document.getElementById('setupBody').innerHTML='<div class="empty-state"><div class="empty-icon">⊡</div>Enter ticker and load setup</div>';
  document.getElementById('setupSymbol').innerHTML='—';
  document.getElementById('entryBody').innerHTML='<div style="color:var(--text3);font-family:var(--mono);font-size:11px;">Load a setup to enable entry actions.</div>';
  document.getElementById('livePriceDisplay').style.display='none';
  document.getElementById('manageEmpty').style.display='block';
  document.getElementById('trancheGrid').style.display='none';
  document.getElementById('posSummary').style.display='none';
  document.getElementById('ordersTable').style.display='none';
  document.getElementById('ordersLabel').style.display='none';
  document.getElementById('trancheLabel').style.display='none';
  document.getElementById('stopModeLabel').textContent='';
  document.getElementById('positionSummaryHeader').textContent='No position';
  document.getElementById('exitPlanContent').innerHTML='';
  document.getElementById('stopPlanContent').innerHTML='';
  ['stop1Btn','stop2Btn','stop3Btn','p1Btn','p2Btn','p3Btn','beBtn','allBeBtn','refreshBtn','flattenBtn'].forEach(id=>{const el=document.getElementById(id);if(el){el.disabled=true;el.classList.remove('active');}});
  setState('idle');
  log('Cockpit reset.','sys');
});

window.addEventListener('load',()=>{
  document.getElementById('tickerInput').value='AAPL';
  setTimeout(loadSetup,300);
});
</script>
</body>
</html>

```

---

## Instructions for Claude Code

1. Read the HTML above completely before writing any code
2. The `state` object in the JS is the exact shape your backend must match
3. The `MOCK` object shows the exact data structure each symbol needs
4. Every function in the JS maps to a backend endpoint — do not change function signatures
5. Replace `MOCK` lookups with `fetch('/api/setup/{symbol}')`
6. Replace `setInterval(tickPrice, 2000)` with a WebSocket connection to `WS /ws/price/{symbol}`
7. Keep all CSS variables and class names intact — do not restyle anything
8. The `addOrder()` function must call `POST /api/orders` and return the broker order ID
9. All `state.orders.push()` calls must be mirrored to the database
10. On page load, call `GET /api/positions` to rehydrate state for any open positions
