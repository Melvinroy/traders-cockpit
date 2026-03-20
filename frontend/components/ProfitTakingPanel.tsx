import { OrdersBlotter } from "@/components/OrdersBlotter";
import { activeShares, f2, fp, soldShares, splitShares, targetPrice, trailingStop } from "@/lib/cockpit-ui";
import type { OrderView, PositionView, SetupResponse, Tranche, TrancheMode } from "@/lib/types";

type Props = {
  setup: SetupResponse | null;
  activePosition: PositionView | null;
  trancheCount: number;
  trancheModes: TrancheMode[];
  tranches: Tranche[];
  orders: OrderView[];
  onTrancheCountChange: (value: number) => void;
  onTrancheModeChange: (index: number, value: TrancheMode) => void;
  onExecute: () => void;
};

export function ProfitTakingPanel(props: Props) {
  const { setup, activePosition, trancheCount, trancheModes, tranches, orders, onTrancheCountChange, onTrancheModeChange, onExecute } = props;
  const plannedShares = setup ? splitShares(setup.shares, trancheCount) : [];
  const activeQty = activePosition ? activeShares(activePosition) : 0;
  const soldQty = activePosition ? soldShares(activePosition) : 0;
  const plannedSetup = setup;
  const canExecuteProfit = activePosition ? ["protected", "P1_done", "P2_done", "runner_only"].includes(activePosition.phase) : false;

  return (
    <div className="panel manage-panel">
      <div className="panel-header profit-header">
        <div className="panel-title">Profit Taking</div>
        <div className="profit-controls">
          <span className="protect-caption">TRANCHES</span>
          <button type="button" className={`tranche-count-btn ${trancheCount === 1 ? "active" : ""}`} onClick={() => onTrancheCountChange(1)}>P1</button>
          <button type="button" className={`tranche-count-btn ${trancheCount === 2 ? "active" : ""}`} onClick={() => onTrancheCountChange(2)}>P1{"\u00B7"}P2</button>
          <button type="button" className={`tranche-count-btn ${trancheCount === 3 ? "active" : ""}`} onClick={() => onTrancheCountChange(3)}>P1{"\u00B7"}P2{"\u00B7"}P3</button>
          <button type="button" className="stop-ok-btn" disabled={!canExecuteProfit} onClick={onExecute}>EXECUTE</button>
          <div className="position-summary-header">{activePosition ? `${activeQty}sh active / ${soldQty}sh sold` : "No position"}</div>
        </div>
      </div>
      <div className="exit-plan-shell">
        <div className="section-label stop-plan-title">Exit Plan</div>
        <div className="exit-plan-content">
          {!plannedSetup ? null : trancheModes.slice(0, trancheCount).map((mode, index) => {
            const price = mode.mode === "runner" ? trailingStop(activePosition?.livePrice ?? plannedSetup.last, mode) : targetPrice(plannedSetup, mode);
            const qty = plannedShares[index] ?? 0;
            return (
              <div className="exit-plan-line" key={`exit-${index}`}>
                <span className="plan-line-label">P{index + 1}</span>
                <button
                  type="button"
                  className={`mode-toggle ${mode.mode === "runner" ? "runner" : "limit"}`}
                  onClick={() =>
                    onTrancheModeChange(index, {
                      ...mode,
                      mode: mode.mode === "runner" ? "limit" : "runner"
                    })
                  }
                >
                  {mode.mode === "runner" ? "RUNNER" : "LIMIT"}
                </button>
                <span className="plan-pct">{qty ? `${Math.round((qty / plannedSetup.shares) * 100)}%` : "-"}</span>
                <span className="plan-price">{price !== null ? fp(price) : "-"}</span>
                <span className="plan-qty">{qty} sh</span>
                {mode.mode === "runner" ? (
                  <div className="runner-input-wrap">
                    <input
                      type="number"
                      inputMode="decimal"
                      className="trail-input"
                      value={mode.trail}
                      onChange={(event) => onTrancheModeChange(index, { ...mode, trail: Number(event.target.value) })}
                    />
                    <button
                      type="button"
                      className="trail-unit-toggle"
                      onClick={() => onTrancheModeChange(index, { ...mode, trailUnit: mode.trailUnit === "$" ? "%" : "$" })}
                    >
                      {mode.trailUnit}
                    </button>
                  </div>
                ) : (
                  <div className="target-toggle-wrap">
                    <select
                      className="plan-select compact"
                      value={mode.target}
                      onChange={(event) => onTrancheModeChange(index, { ...mode, target: event.target.value as TrancheMode["target"] })}
                    >
                      <option value="1R">1R</option>
                      <option value="2R">2R</option>
                      <option value="3R">3R</option>
                      <option value="Manual">Manual</option>
                    </select>
                    {mode.target === "Manual" ? (
                      <input
                        type="number"
                        inputMode="decimal"
                        className="manual-price-input"
                        value={mode.manualPrice ?? 0}
                        onChange={(event) => onTrancheModeChange(index, { ...mode, manualPrice: Number(event.target.value) })}
                      />
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="manage-scroll">
        <div className="section-label" style={{ display: tranches.length ? "block" : "none" }}>Exits</div>
        {tranches.length ? (
          <>
            <div className="tranche-grid">
              {tranches.map((tranche) => {
                const pnl = tranche.status === "sold" && tranche.target ? (tranche.target - (setup?.entry ?? 0)) * tranche.qty : null;
                return (
                  <div key={tranche.id} className={`tranche-card ${tranche.status}`}>
                    <div className="tranche-label">{tranche.id} {"\u00B7"} {tranche.label.split("·").slice(-1)[0]?.trim() ?? tranche.label}</div>
                    <div className="tranche-qty">{tranche.qty} <span className="tranche-unit">sh</span></div>
                    <div className="tranche-stop">{"\u2193"} STOP {fp(tranche.stop)}</div>
                    <div className="tranche-target">{tranche.target ? `${"\u2191"} TGT ${fp(tranche.target)}` : `${"\u2191"} ${tranche.mode.toUpperCase()}`}</div>
                    {pnl !== null ? (
                      <div className={`tranche-pnl ${pnl >= 0 ? "green" : "red"}`}>{pnl >= 0 ? "+" : ""}{f2(pnl)}</div>
                    ) : null}
                    <div className={`tranche-status status-${tranche.status}`}>
                      <span className="status-dot" />
                      {tranche.status.toUpperCase()}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="pos-summary">
              <div className="pos-item"><div className="pos-item-label">Total Shares</div><div className="pos-item-val">{setup?.shares ?? 0}</div></div>
              <div className="pos-item"><div className="pos-item-label">Active</div><div className="pos-item-val green">{activeQty} sh</div></div>
              <div className="pos-item"><div className="pos-item-label">Sold</div><div className="pos-item-val">{soldQty} sh</div></div>
              <div className="pos-item"><div className="pos-item-label">Entry</div><div className="pos-item-val">{fp(setup?.entry)}</div></div>
              <div className="pos-item"><div className="pos-item-label">Notional</div><div className="pos-item-val">{f2((setup?.entry ?? 0) * activeQty)}</div></div>
            </div>
            <div className="section-label">Orders</div>
            <OrdersBlotter orders={orders} />
          </>
        ) : (
          <div id="manageEmpty" className="empty-state">
            <div className="empty-icon">{"\u25C8"}</div>
            Set stop protection, then take profits manually
          </div>
        )}
      </div>
    </div>
  );
}
