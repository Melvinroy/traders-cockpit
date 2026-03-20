import type { PositionView } from "@/lib/types";
import { activeShares, fp, isActivePhase, signedMoney } from "@/lib/cockpit-ui";

type Props = {
  positions: PositionView[];
  activeSymbol: string;
  onSelect: (symbol: string) => void;
};

export function OpenPositionsList({ positions, activeSymbol, onSelect }: Props) {
  const openPositions = positions.filter((position) => isActivePhase(position.phase));
  if (!openPositions.length) {
    return null;
  }

  return (
    <div className="open-positions-section">
      <div className="op-section-label">
        <span>
          Open Positions <span className="op-count">({openPositions.length})</span>
        </span>
        <span className="op-live-badge">{"\u25CF"} LIVE</span>
      </div>
      {openPositions.map((position) => {
        const live = position.livePrice || position.setup.entry;
        const activeQty = activeShares(position);
        const pnl = (live - position.setup.entry) * activeQty;
        const stopEnabled = position.stopMode > 0;
        const profitEnabled = position.phase !== "trade_entered";
        const isActive = position.symbol === activeSymbol;

        return (
          <button
            key={position.symbol}
            type="button"
            className={`op-card ${isActive ? "expanded" : ""}`}
            onClick={() => onSelect(position.symbol)}
          >
            <div className="op-card-header">
              <div className="op-top-row">
                <span className="op-symbol">{position.symbol}</span>
                <span className={`op-pnl ${pnl >= 0 ? "op-pnl-pos" : "op-pnl-neg"}`}>{signedMoney(pnl)}</span>
              </div>
              <div className="op-metrics-row">
                <div>
                  <span className="op-key">ENTRY</span>
                  <br />
                  <span className="op-val">{fp(position.setup.entry)}</span>
                </div>
                <div>
                  <span className="op-key">LIVE</span>
                  <br />
                  <span className="op-val">{fp(live)}</span>
                </div>
                <div className="op-status-wrap">
                  <span className={`op-badge ${stopEnabled ? "op-badge-live" : "op-badge-off"}`}>STOP {stopEnabled ? "SET" : "\u2014"}</span>
                  <span className={`op-badge ${profitEnabled ? "op-badge-info" : "op-badge-off"}`}>PROFIT {profitEnabled ? "ON" : "\u2014"}</span>
                </div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
