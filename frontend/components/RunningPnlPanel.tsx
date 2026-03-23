"use client";

import { f2, formatLogTime, fp, runningPnlSummary } from "@/lib/cockpit-ui";
import type { PositionView, SetupResponse } from "@/lib/types";

type Props = {
  activePosition: PositionView | null;
  setup: SetupResponse | null;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
};

export function RunningPnlPanel({ activePosition, setup, collapsed = false, onToggleCollapse }: Props) {
  const pnlSummary = runningPnlSummary(activePosition, setup);

  return (
    <div className={`panel running-pnl-panel ${collapsed ? "panel-collapsed" : ""}`}>
      <div className="panel-header">
        <div className="panel-title-row panel-title-row-clickable" onClick={onToggleCollapse}>
          <button
            type="button"
            className="panel-collapse-btn"
            onClick={(event) => {
              event.stopPropagation();
              onToggleCollapse?.();
            }}
          >
            {collapsed ? "+" : "-"}
          </button>
          <div className="panel-title">Running P&amp;L</div>
        </div>
        <div className="position-summary-header">
          {pnlSummary ? `${pnlSummary.remainingShares}sh open / ${pnlSummary.closedShares}sh closed` : "No filled position"}
        </div>
      </div>
      {!collapsed ? (
        <div className="panel-body running-pnl-body">
          {pnlSummary ? (
            <>
              <div className="running-pnl-grid">
                <div className="running-pnl-card">
                  <div className="running-pnl-label">Total Shares</div>
                  <div className="running-pnl-value">{pnlSummary.totalShares}</div>
                </div>
                <div className="running-pnl-card">
                  <div className="running-pnl-label">Closed</div>
                  <div className="running-pnl-value">{pnlSummary.closedShares} sh</div>
                </div>
                <div className="running-pnl-card">
                  <div className="running-pnl-label">Remaining</div>
                  <div className="running-pnl-value green">{pnlSummary.remainingShares} sh</div>
                </div>
                <div className="running-pnl-card">
                  <div className="running-pnl-label">Realized P&amp;L</div>
                  <div className={`running-pnl-value ${pnlSummary.realizedPnl >= 0 ? "green" : "red"}`}>
                    {pnlSummary.realizedPnl >= 0 ? "+" : "-"}
                    {f2(Math.abs(pnlSummary.realizedPnl))}
                  </div>
                </div>
                <div className="running-pnl-card">
                  <div className="running-pnl-label">Open P&amp;L</div>
                  <div className={`running-pnl-value ${pnlSummary.unrealizedPnl >= 0 ? "green" : "red"}`}>
                    {pnlSummary.unrealizedPnl >= 0 ? "+" : "-"}
                    {f2(Math.abs(pnlSummary.unrealizedPnl))}
                  </div>
                </div>
                <div className="running-pnl-card">
                  <div className="running-pnl-label">Open Risk</div>
                  <div className="running-pnl-value red">-{f2(Math.abs(pnlSummary.openRisk))}</div>
                </div>
              </div>
              <div className="running-pnl-legs">
                <div className="running-pnl-legs-header">Filled Legs</div>
                {pnlSummary.filledLegs.length ? (
                  pnlSummary.filledLegs.map((leg) => (
                    <div className="running-pnl-leg" key={`${leg.label}-${leg.filledAt ?? leg.qty}`}>
                      <span className="running-pnl-leg-label">{leg.label}</span>
                      <span className="running-pnl-leg-qty">{leg.qty} sh</span>
                      <span className="running-pnl-leg-price">{leg.exitPrice !== null ? fp(leg.exitPrice) : "-"}</span>
                      <span className={`running-pnl-leg-pnl ${leg.pnl >= 0 ? "green" : "red"}`}>
                        {leg.pnl >= 0 ? "+" : "-"}
                        {f2(Math.abs(leg.pnl))}
                      </span>
                      <span className="running-pnl-leg-time">{leg.filledAt ? formatLogTime(leg.filledAt) : "-"}</span>
                    </div>
                  ))
                ) : (
                  <div className="running-pnl-empty">No partial exits filled yet.</div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">◇</div>
              Running P&amp;L appears after a real fill and updates through partial exits.
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
