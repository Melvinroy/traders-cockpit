# Final UI Parity 50 Checklist

Branch: `codex/feature-final-ui-parity`

Status: complete for this tranche

## Runtime and QC
- [x] Frontend dev app serves on `127.0.0.1:3010`
- [x] Backend health is reachable during local QC
- [x] `run-qc.ps1` completes successfully
- [x] Playwright root-page smoke passes
- [x] Playwright `LOAD SETUP` flow passes
- [x] Playwright `ENTER TRADE` flow passes
- [x] Playwright stop execution flow passes
- [x] Playwright profit execution flow passes
- [x] Backend pytest suite passes
- [x] Frontend lint passes

## Header and Global State
- [x] Header title matches `TRADER'S / COCKPIT`
- [x] Ticker input keeps `$` prefix treatment
- [x] `LOAD SETUP` copy matches prototype
- [x] `RESET` copy matches prototype
- [x] paper badge renders as `● PAPER`
- [x] phase badge uses explicit prototype labels
- [x] live price area stays hidden until priced state exists
- [x] reset clears the ticker field instead of forcing a symbol

## Left Rail Fidelity
- [x] idle setup header symbol shows `—`
- [x] loaded setup header symbol switches to large ticker treatment
- [x] empty left-rail state matches prototype copy
- [x] quote block renders bid/ask/suggested entry
- [x] stop levels block renders LoD, ATR, and final stop
- [x] risk sizing block renders equity, risk percent, dollar risk, per-share risk, and shares
- [x] reference block renders SMA, RVOL, extension, and days-to-cover values
- [x] risk percent input keeps prototype-like inline editor behavior
- [x] open positions section only renders when active positions exist
- [x] open positions count and live badge match prototype treatment
- [x] active open-position card expands into lower detail area

## Center Column Fidelity
- [x] idle trade-entry copy matches prototype
- [x] setup-stage entry panel renders exact core controls
- [x] setup-stage stop plan previews render before trade entry
- [x] setup-stage stop header shows `NOT SET`
- [x] setup-stage stop hint shows `— Enter trade first`
- [x] stop execute button only arms when a trade exists
- [x] `ALL → BE` copy matches prototype
- [x] `⬛ FLATTEN` copy matches prototype
- [x] profit header uses `TRANCHES` caption and `P1 / P1·P2 / P1·P2·P3`
- [x] profit execute button only arms when a protected/profit-managed position exists
- [x] manage empty state matches prototype copy
- [x] runner-only state preserves the runner card in Exits
- [x] tranche P&L uses signed dollar formatting
- [x] notional value uses dollar formatting

## Orders and Log Fidelity
- [x] orders blotter uses root/child hierarchy rows
- [x] reduced stop quantities display as `0(94)` style notation
- [x] order timestamps render in the status column
- [x] log panel keeps `SYS` seed row on empty state
- [x] log timestamps render in 24-hour format
- [x] trade-entry log copy includes `(MKT simulated)` like the prototype
- [x] tranche allocation gets its own `SYS` log line
- [x] stop-application log uses the detailed `✓ Stops applied — ...` form
- [x] profit execution log uses `✓ Profit plan executed — ...`
- [x] stale-order recovery no longer pollutes the visible cockpit log

## Recovery and Safety
- [x] closed positions are not auto-hydrated as active on boot
- [x] stale active orders for a closed symbol are auto-canceled before new entry
- [x] stale-order recovery has backend regression coverage
- [x] order ID generation is sequence-safe across recovery scenarios
