"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { CatalystDashboardResponse, CatalystDirection, CatalystRow } from "@/lib/types";

type WindowDays = 1 | 3 | 5;
type DirectionFilter = "all" | CatalystDirection;

const WINDOWS: { label: string; value: WindowDays }[] = [
  { label: "TODAY", value: 1 },
  { label: "3D", value: 3 },
  { label: "5D", value: 5 },
];

function gradeLabel(value: string) {
  if (value.startsWith("A+")) return "A+";
  if (value.startsWith("A ")) return "A";
  if (value.startsWith("B ")) return "B";
  if (value === "No Fresh Catalyst") return "NFC";
  if (value === "Sympathy / Continuation") return "CONT";
  return "N";
}

function importanceBand(score: number) {
  if (score >= 96) return "critical";
  if (score >= 82) return "high";
  if (score >= 62) return "medium";
  return "low";
}

function formatGenerated(value: string) {
  try {
    return new Intl.DateTimeFormat("en-SG", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Singapore" }).format(new Date(value));
  } catch {
    return value;
  }
}

function SignalCard({ row, rank }: { row: CatalystRow; rank: number }) {
  return (
    <article className={`catalyst-signal-card signal-${row.direction} importance-${importanceBand(row.importance_score)}`}>
      <div className="catalyst-signal-rank">{String(rank).padStart(2, "0")}</div>
      <div className="catalyst-signal-main">
        <div className="catalyst-signal-line">
          <strong>{row.ticker}</strong>
          <span className={`catalyst-grade grade-${row.direction}`}>{gradeLabel(row.catalyst_quality_direction)}</span>
          <span className="catalyst-score">{row.importance_score}</span>
        </div>
        <div className="catalyst-signal-title">{row.primary_catalyst_category} · {row.theme}</div>
        <p>{row.trade_read}</p>
        <div className="catalyst-signal-meta">
          <span>{row.move_already_done}</span>
          <span>{row.source_confidence} confidence</span>
          {row.appearances > 1 ? <span>{row.appearances}× in window</span> : null}
        </div>
      </div>
    </article>
  );
}

export function CatalystDashboard() {
  const [days, setDays] = useState<WindowDays>(1);
  const [direction, setDirection] = useState<DirectionFilter>("all");
  const [search, setSearch] = useState("");
  const [data, setData] = useState<CatalystDashboardResponse | null>(null);
  const [selected, setSelected] = useState<CatalystRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getCatalysts(days)
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setSelected((current) => current ? payload.rows.find((row) => row.ticker === current.ticker) ?? null : null);
        setError(null);
      })
      .catch((reason) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Unable to load catalyst data.");
      })
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [days]);

  const rows = data?.rows ?? [];
  const filtered = useMemo(() => {
    const query = search.trim().toUpperCase();
    return rows.filter((row) => {
      if (direction !== "all" && row.direction !== direction) return false;
      if (!query) return true;
      return [row.ticker, row.theme, row.sector, row.primary_catalyst_category, row.catalyst_tags].some((value) => value.toUpperCase().includes(query));
    });
  }, [direction, rows, search]);

  const ranked = useMemo(() => [...rows].sort((a, b) => b.importance_score - a.importance_score || b.appearances - a.appearances), [rows]);
  const bullish = ranked.filter((row) => row.direction === "bullish");
  const bearish = ranked.filter((row) => row.direction === "bearish");
  const highConviction = rows.filter((row) => row.catalyst_quality_direction.startsWith("A") && row.source_confidence === "High").length;
  const directCount = rows.filter((row) => row.direct_sympathy_sector_move === "Direct").length;
  const themeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    rows.forEach((row) => counts.set(row.theme, (counts.get(row.theme) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [rows]);
  const latestReport = data?.reports?.[0] ?? null;

  return (
    <section className="catalyst-dashboard">
      <div className="catalyst-commandbar">
        <div>
          <div className="catalyst-kicker">CATALYST INTELLIGENCE</div>
          <h1>Executive Signal Board</h1>
          <p>Ranked, de-duplicated catalyst inventory from the locked Catalyst_Table_v2 workflow.</p>
        </div>
        <div className="catalyst-command-actions">
          <div className="catalyst-window-switch" aria-label="Catalyst date range">
            {WINDOWS.map((window) => <button key={window.value} type="button" className={days === window.value ? "active" : ""} onClick={() => setDays(window.value)}>{window.label}</button>)}
          </div>
          <div className="catalyst-asof">AS OF <strong>{data?.as_of_date ?? "—"}</strong></div>
        </div>
      </div>

      {error ? <div className="runtime-banner">{error}</div> : null}
      {data?.status === "unavailable" ? <div className="catalyst-empty">Catalyst dataset is not available in this environment. Journal remains fully operational.</div> : null}

      <div className="catalyst-kpi-grid">
        <div className="catalyst-kpi"><span>ACTIVE NAMES</span><strong>{rows.length}</strong><small>{days === 1 ? "latest trading day" : `latest ${days} calendar days`}</small></div>
        <div className="catalyst-kpi catalyst-kpi-positive"><span>BULLISH</span><strong>{bullish.length}</strong><small>{bullish.filter((row) => row.catalyst_quality_direction.startsWith("A")).length} A-tier</small></div>
        <div className="catalyst-kpi catalyst-kpi-negative"><span>BEARISH</span><strong>{bearish.length}</strong><small>{bearish.filter((row) => row.catalyst_quality_direction.startsWith("A")).length} A-tier</small></div>
        <div className="catalyst-kpi"><span>HIGH CONVICTION</span><strong>{highConviction}</strong><small>High confidence · A tier</small></div>
        <div className="catalyst-kpi"><span>DIRECT</span><strong>{directCount}</strong><small>{rows.length ? Math.round((directCount / rows.length) * 100) : 0}% of inventory</small></div>
      </div>

      <div className="catalyst-leadership-grid">
        <div className="catalyst-panel catalyst-leader-panel">
          <div className="catalyst-panel-head"><div><span>LEADERSHIP</span><h2>Bullish priority</h2></div><span className="catalyst-count positive">{bullish.length}</span></div>
          <div className="catalyst-signal-stack">{bullish.slice(0, 4).map((row, index) => <SignalCard key={row.ticker} row={row} rank={index + 1} />)}</div>
        </div>
        <div className="catalyst-panel catalyst-leader-panel">
          <div className="catalyst-panel-head"><div><span>RISK BOARD</span><h2>Bearish priority</h2></div><span className="catalyst-count negative">{bearish.length}</span></div>
          <div className="catalyst-signal-stack">{bearish.slice(0, 4).map((row, index) => <SignalCard key={row.ticker} row={row} rank={index + 1} />)}</div>
        </div>
        <div className="catalyst-panel catalyst-context-panel">
          <div className="catalyst-panel-head"><div><span>TAPE CONTEXT</span><h2>Theme concentration</h2></div></div>
          <div className="catalyst-theme-list">
            {themeCounts.map(([theme, count]) => <div className="catalyst-theme-row" key={theme}><div><strong>{theme}</strong><span>{count} name{count === 1 ? "" : "s"}</span></div><div className="catalyst-theme-bar"><i style={{ width: `${Math.max(12, (count / Math.max(1, themeCounts[0]?.[1] ?? 1)) * 100)}%` }} /></div></div>)}
          </div>
          {latestReport ? <div className="catalyst-latest-report"><span>LATEST BRIEF · {formatGenerated(latestReport.generated_at_sgt)} SGT</span><strong>{latestReport.report_type}</strong><p>{latestReport.best_focus ?? latestReport.market_summary ?? "No focus note."}</p></div> : null}
        </div>
      </div>

      <div className="catalyst-panel catalyst-table-panel">
        <div className="catalyst-table-toolbar">
          <div><span>CANONICAL INVENTORY</span><h2>Signal scanner</h2></div>
          <div className="catalyst-filterbar">
            {(["all", "bullish", "bearish", "neutral"] as DirectionFilter[]).map((item) => <button type="button" key={item} className={direction === item ? "active" : ""} onClick={() => setDirection(item)}>{item.toUpperCase()}</button>)}
            <input aria-label="Search catalyst inventory" placeholder="Ticker / theme / sector" value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>
        </div>
        <div className="catalyst-table-wrap">
          <table className="catalyst-table">
            <thead><tr><th>Signal</th><th>Ticker</th><th>Grade</th><th>Catalyst</th><th>Theme</th><th>Move</th><th>Freshness</th><th>Confidence</th><th>Action</th></tr></thead>
            <tbody>
              {filtered.map((row) => <tr key={row.ticker} className={`row-${row.direction}`} onClick={() => setSelected(row)}>
                <td><span className={`importance-dot importance-${importanceBand(row.importance_score)}`} title={`Importance ${row.importance_score}`} /><b>{row.importance_score}</b></td>
                <td><strong className="catalyst-ticker">{row.ticker}</strong>{row.appearances > 1 ? <small>{row.appearances}×</small> : null}</td>
                <td><span className={`catalyst-grade grade-${row.direction}`}>{gradeLabel(row.catalyst_quality_direction)}</span></td>
                <td><strong>{row.primary_catalyst_category}</strong><small>{row.direct_sympathy_sector_move}</small></td>
                <td>{row.theme}</td><td>{row.move_already_done}</td><td>{row.freshness_catalyst_age}</td><td>{row.source_confidence}</td><td>{row.action_priority}</td>
              </tr>)}
            </tbody>
          </table>
          {!loading && filtered.length === 0 ? <div className="catalyst-empty">No catalysts match this view.</div> : null}
          {loading ? <div className="catalyst-empty">Loading catalyst intelligence…</div> : null}
        </div>
      </div>

      {selected ? <div className="catalyst-detail-backdrop" role="presentation" onClick={() => setSelected(null)}><aside className="catalyst-detail" role="dialog" aria-modal="true" aria-label={`${selected.ticker} catalyst detail`} onClick={(event) => event.stopPropagation()}>
        <button type="button" className="catalyst-detail-close" onClick={() => setSelected(null)}>×</button>
        <div className="catalyst-detail-top"><span className={`catalyst-grade grade-${selected.direction}`}>{selected.catalyst_quality_direction}</span><span>{selected.importance_score}/100</span></div>
        <h2>{selected.ticker}</h2><h3>{selected.primary_catalyst_category} · {selected.theme}</h3>
        <div className="catalyst-detail-section"><span>CATALYST</span><p>{selected.catalyst_summary}</p></div>
        <div className="catalyst-detail-section"><span>TRADE READ</span><p>{selected.trade_read}</p></div>
        <div className="catalyst-detail-section risk"><span>RISK / INVALIDATOR</span><p>{selected.risk_invalidator}</p></div>
        <dl className="catalyst-detail-grid"><div><dt>Move</dt><dd>{selected.move_already_done}</dd></div><div><dt>Liquidity</dt><dd>{selected.volume_liquidity_confirmation}</dd></div><div><dt>Freshness</dt><dd>{selected.freshness_catalyst_age}</dd></div><div><dt>Source</dt><dd>{selected.primary_source_evidence}</dd></div><div><dt>Session</dt><dd>{selected.catalyst_release_session}</dd></div><div><dt>Related</dt><dd>{selected.sympathy_related_tickers}</dd></div></dl>
      </aside></div> : null}
    </section>
  );
}
