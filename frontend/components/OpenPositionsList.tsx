import type { PositionView } from "@/lib/types";

type Props = {
  positions: PositionView[];
  activeSymbol: string;
  onSelect: (symbol: string) => void;
};

export function OpenPositionsList({ positions, activeSymbol, onSelect }: Props) {
  const openPositions = positions.filter((position) => position.phase !== "closed");
  if (!openPositions.length) {
    return null;
  }
  return (
    <div>
      <div className="op-section-label">
        Open Positions <span>({openPositions.length})</span>
      </div>
      {openPositions.map((position) => {
        const entry = position.setup.entry;
        const activeQty = position.tranches.filter((tranche) => tranche.status === "active").reduce((sum, tranche) => sum + tranche.qty, 0);
        const pnl = (position.livePrice - entry) * activeQty;
        return (
          <button
            type="button"
            key={position.symbol}
            className={`op-card ${activeSymbol === position.symbol ? "expanded" : ""}`}
            onClick={() => onSelect(position.symbol)}
          >
            <div className="op-card-header">
              <div className="op-top-row">
                <span className="op-symbol">{position.symbol}</span>
                <span className={`op-pnl ${pnl >= 0 ? "op-pnl-pos" : "op-pnl-neg"}`}>{pnl.toFixed(2)}</span>
              </div>
              <div className="op-meta-grid">
                <div>
                  <span className="op-key">ENTRY</span>
                  <span className="op-val">{entry.toFixed(2)}</span>
                </div>
                <div>
                  <span className="op-key">LIVE</span>
                  <span className="op-val">{position.livePrice.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
