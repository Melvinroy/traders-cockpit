import type { OrderView, Tranche, TrancheMode } from "@/lib/types";
import { OrdersBlotter } from "@/components/OrdersBlotter";

type Props = {
  trancheCount: number;
  trancheModes: TrancheMode[];
  tranches: Tranche[];
  orders: OrderView[];
  onTrancheCountChange: (value: number) => void;
  onTrancheModeChange: (index: number, value: TrancheMode) => void;
  onExecute: () => void;
};

export function ProfitTakingPanel(props: Props) {
  const { trancheCount, trancheModes, tranches, orders, onTrancheCountChange, onTrancheModeChange, onExecute } = props;
  return (
    <div className="panel manage-panel">
      <div className="panel-header">
        <div className="panel-title">Profit Taking</div>
        <div className="segmented tight">
          <button className={`tranche-count-btn ${trancheCount === 1 ? "active" : ""}`} onClick={() => onTrancheCountChange(1)}>P1</button>
          <button className={`tranche-count-btn ${trancheCount === 2 ? "active" : ""}`} onClick={() => onTrancheCountChange(2)}>P1·P2</button>
          <button className={`tranche-count-btn ${trancheCount === 3 ? "active" : ""}`} onClick={() => onTrancheCountChange(3)}>P1·P2·P3</button>
          <button className="btn btn-amber" onClick={onExecute}>EXECUTE</button>
        </div>
      </div>
      <div className="panel-body">
        {trancheModes.slice(0, trancheCount).map((mode, index) => (
          <div className="plan-row" key={`tranche-mode-${index}`}>
            <span className="plan-label">P{index + 1}</span>
            <button className={`mode-toggle ${mode.mode === "runner" ? "runner" : "limit"}`} onClick={() => onTrancheModeChange(index, { ...mode, mode: mode.mode === "limit" ? "runner" : "limit" })}>
              {mode.mode === "runner" ? "RUNNER" : "LIMIT"}
            </button>
            {mode.mode === "limit" ? (
              <select className="plan-select" value={mode.target} onChange={(event) => onTrancheModeChange(index, { ...mode, target: event.target.value as TrancheMode["target"] })}>
                <option value="1R">1R</option>
                <option value="2R">2R</option>
                <option value="3R">3R</option>
                <option value="Manual">Manual</option>
              </select>
            ) : (
              <input className="plan-input" type="number" value={mode.trail} onChange={(event) => onTrancheModeChange(index, { ...mode, trail: Number(event.target.value) })} />
            )}
            <span className="plan-hint">{tranches[index]?.qty ?? 0} sh</span>
          </div>
        ))}
        <div className="tranche-grid">
          {tranches.map((tranche) => (
            <div key={tranche.id} className={`tranche-card ${tranche.status}`}>
              <div className="tranche-label">{tranche.id}</div>
              <div className="tranche-qty">{tranche.qty} sh</div>
              <div className="tranche-stop">STOP {tranche.stop.toFixed(2)}</div>
              <div className="tranche-target">{tranche.target ? `TARGET ${tranche.target.toFixed(2)}` : tranche.mode.toUpperCase()}</div>
            </div>
          ))}
        </div>
        <OrdersBlotter orders={orders} />
      </div>
    </div>
  );
}
