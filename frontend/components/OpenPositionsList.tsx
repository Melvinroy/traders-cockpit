"use client";

import type { PositionView } from "@/lib/types";
import { activeShares, isActivePhase, signedMoney } from "@/lib/cockpit-ui";

type Props = {
  positions: PositionView[];
  activeSymbol: string;
  onSelect: (symbol: string) => void;
};

function profitEnabled(position: PositionView, activeSymbol: string): boolean {
  if (position.symbol !== activeSymbol) return false;
  return ["protected", "P1_done", "P2_done", "runner_only"].includes(position.phase);
}

export function OpenPositionsList({ positions, activeSymbol, onSelect }: Props) {
  const openPositions = positions.filter((position) => isActivePhase(position.phase));

  return (
    <div className="open-positions-section">
      {!openPositions.length ? (
        <div className="empty-state op-empty-state">
          <div className="empty-icon">{"\u25C8"}</div>
          No open positions
        </div>
      ) : (
        <>
          <div className="op-list-header" aria-hidden="true">
            <span className="op-list-heading">Symbol</span>
            <span className="op-list-heading op-list-heading-pnl">U P&amp;L</span>
            <span className="op-list-heading op-list-heading-badge">S</span>
            <span className="op-list-heading op-list-heading-badge">P</span>
          </div>
          <div className="op-list">
            {openPositions.map((position) => {
              const live = position.livePrice || position.setup.entry;
              const activeQty = activeShares(position);
              const pnl = (live - position.setup.entry) * activeQty;
              const stopEnabled = position.stopMode > 0;
              const isProfitEnabled = profitEnabled(position, activeSymbol);
              const isSelected = position.symbol === activeSymbol;

              return (
                <button
                  key={position.symbol}
                  type="button"
                  className={`op-row ${isSelected ? "active" : ""}`}
                  onClick={() => onSelect(position.symbol)}
                >
                  <span className="op-row-symbol">{position.symbol}</span>
                  <span className={`op-row-pnl ${pnl >= 0 ? "op-pnl-pos" : "op-pnl-neg"}`}>{signedMoney(pnl)}</span>
                  <span
                    className={`op-badge op-badge-letter ${stopEnabled ? "op-badge-live" : "op-badge-danger"}`}
                    title={stopEnabled ? "Stop protection active" : "No stop protection active"}
                  >
                    S
                  </span>
                  <span
                    className={`op-badge op-badge-letter ${isProfitEnabled ? "op-badge-info" : "op-badge-off"}`}
                    title={isProfitEnabled ? "Profit taking active" : "No profit taking active"}
                  >
                    P
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
