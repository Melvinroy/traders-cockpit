import "@testing-library/jest-dom/vitest";

Object.defineProperty(globalThis, "fetch", {
  writable: true,
  value: async (input: RequestInfo | URL) => {
    const url = String(input);
    const payload =
      url.includes("/api/auth/me")
        ? {
            username: "admin",
            role: "admin",
            expires_at: new Date(Date.now() + 60_000).toISOString()
          }
        : url.includes("/api/auth/login")
          ? {
              username: "admin",
              role: "admin",
              expires_at: new Date(Date.now() + 60_000).toISOString()
            }
          : url.includes("/api/auth/logout")
            ? { ok: true }
            : url.includes("/api/account")
        ? {
            equity: 25000,
            buying_power: 100000,
            risk_pct: 1,
            mode: "paper",
            effective_mode: "paper",
            daily_realized_pnl: 0,
            allow_live_trading: false,
            max_position_notional_pct: 100,
            daily_loss_limit_pct: 2,
            max_open_positions: 6,
            live_disabled_reason: null
          }
          : url.includes("/api/positions")
          ? []
          : url.includes("/api/activity-log")
            ? []
            : {
                symbol: "AAPL",
                provider: "mock",
                quoteTimestamp: new Date().toISOString(),
                entryBasis: "bid_ask_midpoint",
                stopReferenceDefault: "lod",
                entry: 213.88,
                finalStop: 210.4,
                last: 213.88,
                bid: 213.85,
                ask: 213.92,
                shares: 100,
                riskPct: 1,
                accountEquity: 25000
              };
    return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
  }
});

class MockWebSocket {
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  constructor() {
    queueMicrotask(() => this.onopen?.());
  }
  close() {}
  send() {}
}

Object.defineProperty(globalThis, "WebSocket", {
  writable: true,
  value: MockWebSocket
});
