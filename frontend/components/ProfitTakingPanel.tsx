"use client";

import { fp, splitShares, targetPrice, trailingStop } from "@/lib/cockpit-ui";
import type { PositionView, SetupResponse, TrancheMode } from "@/lib/types";

type Props = {
  setup: SetupResponse | null;
  activePosition: PositionView | null;
  trancheCount: number;
  trancheModes: TrancheMode[];
  executeFlashing?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onTrancheCountChange: (value: number) => void;
  onTrancheModeChange: (index: number, value: TrancheMode) => void;
  onExecute: () => void;
};

export function ProfitTakingPanel(props: Props) {
  const {
    setup,
    activePosition,
    trancheCount,
    trancheModes,
    executeFlashing = false,
    collapsed = false,
    onToggleCollapse,
    onTrancheCountChange,
    onTrancheModeChange,
    onExecute
  } = props;
  const plannedShares = setup
    ? splitShares(setup.shares, trancheCount, trancheModes.slice(0, trancheCount).map((mode) => mode.allocationPct ?? null))
    : [];
  const plannedSetup = setup;
  const canExecuteProfit = activePosition ? ["protected", "P1_done", "P2_done", "runner_only"].includes(activePosition.phase) : false;

  return (
    <div className={`panel manage-panel ${collapsed ? "panel-collapsed" : ""}`}>
      <div className="panel-header profit-header">
        <div className="panel-title-row">
          <button type="button" className="panel-collapse-btn" onClick={onToggleCollapse}>{collapsed ? "+" : "-"}</button>
          <div className="panel-title">Profit Taking</div>
        </div>
        <div className="profit-controls">
          <span className="protect-caption">TRANCHES</span>
          <button type="button" className={`tranche-count-btn ${trancheCount === 1 ? "active" : ""}`} onClick={() => onTrancheCountChange(1)}>P1</button>
          <button type="button" className={`tranche-count-btn ${trancheCount === 2 ? "active" : ""}`} onClick={() => onTrancheCountChange(2)}>P1{"\u00B7"}P2</button>
          <button type="button" className={`tranche-count-btn ${trancheCount === 3 ? "active" : ""}`} onClick={() => onTrancheCountChange(3)}>P1{"\u00B7"}P2{"\u00B7"}P3</button>
          <button type="button" className={`stop-ok-btn ${canExecuteProfit ? "stop-ok-ready" : ""} ${executeFlashing ? "flash" : ""}`} disabled={!canExecuteProfit} onClick={onExecute}>EXECUTE</button>
        </div>
      </div>
      {!collapsed ? <>
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
                <div className="pct-input-wrap">
                  <input
                    type="number"
                    inputMode="decimal"
                    className="pct-input"
                    value={Number((mode.allocationPct ?? 0).toFixed(2))}
                    onChange={(event) => onTrancheModeChange(index, { ...mode, allocationPct: Number(event.target.value) })}
                  />
                  <span className="pct-suffix">%</span>
                </div>
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
      </> : null}
    </div>
  );
}
