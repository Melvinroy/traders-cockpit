
import { useState } from "react";

const COLORS = {
  frontend: { bg: "#1e3a5f", border: "#3b82f6", text: "#93c5fd", label: "#dbeafe" },
  backend: { bg: "#1a3a2a", border: "#22c55e", text: "#86efac", label: "#dcfce7" },
  infra: { bg: "#3b1f1f", border: "#ef4444", text: "#fca5a5", label: "#fee2e2" },
  external: { bg: "#2d1f3b", border: "#a855f7", text: "#d8b4fe", label: "#f3e8ff" },
  arrow: "#94a3b8",
};

function Box({ title, items, color, width = 180 }) {
  return (
    <div style={{
      background: color.bg,
      border: `1.5px solid ${color.border}`,
      borderRadius: 8,
      padding: "10px 14px",
      width,
      minHeight: 40,
    }}>
      <div style={{ color: color.label, fontWeight: 700, fontSize: 12, marginBottom: 6, letterSpacing: 0.5 }}>{title}</div>
      {items.map((item, i) => (
        <div key={i} style={{
          color: color.text,
          fontSize: 11,
          padding: "2px 0",
          borderTop: i === 0 ? `1px solid ${color.border}33` : "none",
          paddingTop: i === 0 ? 4 : 2,
        }}>• {item}</div>
      ))}
    </div>
  );
}

function Label({ text, color }) {
  return (
    <div style={{
      color,
      fontSize: 10,
      fontWeight: 600,
      textAlign: "center",
      letterSpacing: 0.5,
      marginBottom: 2,
    }}>{text}</div>
  );
}

function Arrow({ label, direction = "down", color = COLORS.arrow }) {
  const isHoriz = direction === "right" || direction === "left";
  return (
    <div style={{
      display: "flex",
      flexDirection: isHoriz ? "row" : "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 2,
      padding: isHoriz ? "0 6px" : "4px 0",
    }}>
      <div style={{
        color,
        fontSize: 9,
        textAlign: "center",
        whiteSpace: "nowrap",
        opacity: 0.85,
      }}>{label}</div>
      <div style={{
        color,
        fontSize: isHoriz ? 16 : 14,
        lineHeight: 1,
      }}>
        {direction === "down" ? "↓" : direction === "up" ? "↑" : direction === "right" ? "→" : "←"}
      </div>
    </div>
  );
}

function BiArrow({ label, color = COLORS.arrow }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "4px 0" }}>
      <div style={{ color, fontSize: 9, opacity: 0.85, whiteSpace: "nowrap" }}>{label}</div>
      <div style={{ color, fontSize: 14 }}>⇅</div>
    </div>
  );
}

function Section({ title, color, children, style = {} }) {
  return (
    <div style={{
      border: `1px dashed ${color.border}55`,
      borderRadius: 10,
      padding: "10px 16px 14px",
      background: `${color.bg}55`,
      ...style
    }}>
      <div style={{
        color: color.border,
        fontSize: 11,
        fontWeight: 700,
        marginBottom: 10,
        letterSpacing: 1,
        textTransform: "uppercase",
      }}>{title}</div>
      {children}
    </div>
  );
}

export default function ArchDiagram() {
  return (
    <div style={{
      background: "#0f172a",
      minHeight: "100vh",
      padding: "28px 24px",
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      color: "#e2e8f0",
    }}>
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#f1f5f9", letterSpacing: 0.5 }}>Traders Cockpit — Architecture</div>
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>Component relationships &amp; data flow</div>
      </div>

      {/* Main layout: 3 columns */}
      <div style={{ display: "flex", gap: 24, justifyContent: "center", alignItems: "flex-start" }}>

        {/* ── FRONTEND ── */}
        <Section title="Frontend  ·  Next.js / React  (port 3010)" color={COLORS.frontend} style={{ width: 220 }}>
          <Box title="Auth Layer" color={COLORS.frontend} width={190} items={["LoginPanel", "authUser / authRequired state", "submitLogin / logout", "401 → show login"]} />
          <Arrow label="on auth success" direction="down" color={COLORS.frontend.border} />
          <Box title="Cockpit.tsx  (orchestrator)" color={COLORS.frontend} width={190} items={["Global state manager", "hydrate() — full re-sync", "loadSetup / selectPosition", "WS reconnect + backoff", "runtimeError banner"]} />
          <Arrow label="props" direction="down" color={COLORS.frontend.border} />
          <Box title="UI Panels" color={COLORS.frontend} width={190} items={["CockpitHeader (ticker, price, logout)", "SetupPanel (quote, R-levels, positions)", "EntryPanel (entry, stop, preview, enter)", "StopProtectionPanel (stops, BE, flatten)", "ProfitTakingPanel (tranches, targets)", "ActivityLog (trade log, clear)"]} />
          <Arrow label="REST calls" direction="down" color={COLORS.frontend.border} />
          <Box title="lib/api.ts" color={COLORS.frontend} width={190} items={["ApiError (status-aware)", "getAccount / updateAccount", "getSetup / previewTrade", "enterTrade / applyStops", "executeProfit / moveToBe / flatten", "login / logout / me"]} />
        </Section>

        {/* ── CENTER ARROWS ── */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingTop: 60, gap: 0 }}>
          <BiArrow label="REST HTTP" color="#94a3b8" />
          <div style={{ height: 16 }} />
          <Arrow label="WS events" direction="right" color="#f59e0b" />
          <div style={{ fontSize: 9, color: "#f59e0b", opacity: 0.8, textAlign: "center", marginTop: 2, whiteSpace: "nowrap" }}>price_update</div>
          <div style={{ fontSize: 9, color: "#f59e0b", opacity: 0.8, textAlign: "center", whiteSpace: "nowrap" }}>position_update</div>
          <div style={{ fontSize: 9, color: "#f59e0b", opacity: 0.8, textAlign: "center", whiteSpace: "nowrap" }}>order_update</div>
          <div style={{ fontSize: 9, color: "#f59e0b", opacity: 0.8, textAlign: "center", whiteSpace: "nowrap" }}>log_update</div>
        </div>

        {/* ── BACKEND ── */}
        <Section title="Backend  ·  FastAPI / Python  (port 8010)" color={COLORS.backend} style={{ width: 230 }}>
          <Box title="main.py  (entry point)" color={COLORS.backend} width={200} items={["CORS middleware", "Lifespan: start WS manager, seed DB", "GET /health", "WS /ws/cockpit  ← session auth guard"]} />
          <Arrow label="routes" direction="down" color={COLORS.backend.border} />
          <Box title="API Routes" color={COLORS.backend} width={200} items={["routes_auth  — login / logout / me", "routes_account  — equity, risk%, mode", "routes_market  — setup data", "routes_positions  — positions, orders, logs", "routes_trade  — enter, stops, profit, flatten"]} />
          <Arrow label="delegates all logic" direction="down" color={COLORS.backend.border} />
          <Box title="CockpitService  (business logic)" color={COLORS.backend} width={200} items={["Risk sizing (equity × risk% ÷ per-share-risk)", "Trade lifecycle state machine", "Tranche split & stop grouping", "Order hierarchy (root MKT → STOP/LMT/TRAIL)", "Safety checks (notional, loss limit, dupes)", "Broadcasts WS events after every mutation"]} />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <div>
              <Arrow label="quotes" direction="down" color={COLORS.backend.border} />
              <Box title="MarketDataAdapter" color={COLORS.backend} width={94} items={["AlpacaPolygon", "Fallback local"]} />
            </div>
            <div>
              <Arrow label="orders" direction="down" color={COLORS.backend.border} />
              <Box title="BrokerAdapter" color={COLORS.backend} width={94} items={["Paper (sim)", "Alpaca paper", "_fallback_or_raise"]} />
            </div>
          </div>
          <Arrow label="pub/sub fanout" direction="down" color={COLORS.backend.border} />
          <Box title="WebSocketManager" color={COLORS.backend} width={200} items={["Redis pub/sub (multi-instance)", "Direct broadcast (local fallback)", "connect / disconnect / broadcast"]} />
        </Section>

        {/* ── RIGHT: INFRA + EXTERNAL ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingTop: 40 }}>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <Arrow label="SQL (SQLAlchemy)" direction="left" color={COLORS.infra.border} />
            <Section title="Infrastructure" color={COLORS.infra} style={{ width: 170 }}>
              <Box title="PostgreSQL  (55432)" color={COLORS.infra} width={148} items={["AccountSettingsEntity", "PositionEntity (phase, tranches)", "OrderEntity (MKT/STOP/LMT/TRAIL)", "TradeLogEntity (audit log)"]} />
              <Arrow label="Alembic migrations" direction="down" color={COLORS.infra.border} />
              <Box title="Redis  (56379)" color={COLORS.infra} width={148} items={["WS event pub/sub channel", "Channel prefix scoping", "Multi-instance fanout"]} />
            </Section>
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <Arrow label="HTTP (paper / live)" direction="left" color={COLORS.external.border} />
            <Section title="External" color={COLORS.external} style={{ width: 170 }}>
              <Box title="Alpaca API" color={COLORS.external} width={148} items={["Paper trading endpoint", "Live endpoint (disabled by default)", "ALLOW_LIVE_TRADING guard", "LIVE_CONFIRMATION_TOKEN required"]} />
              <Arrow label="quotes (planned)" direction="down" color={COLORS.external.border} />
              <Box title="Polygon" color={COLORS.external} width={148} items={["Technicals, RVOL", "Days-to-cover", "Roadmap: full integration"]} />
            </Section>
          </div>

        </div>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 20, justifyContent: "center", marginTop: 28 }}>
        {[
          { color: COLORS.frontend.border, label: "Frontend" },
          { color: COLORS.backend.border, label: "Backend" },
          { color: COLORS.infra.border, label: "Infrastructure" },
          { color: COLORS.external.border, label: "External APIs" },
          { color: "#f59e0b", label: "WebSocket events" },
          { color: "#94a3b8", label: "REST / SQL" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
            <span style={{ fontSize: 10, color: "#94a3b8" }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
