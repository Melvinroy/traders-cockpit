import { fp, stopPlanRows } from "@/lib/cockpit-ui";
import type { OrderView, SetupResponse, StopMode, Tranche } from "@/lib/types";

type Props = {
  setup: SetupResponse | null;
  stopMode: number;
  stopModes: StopMode[];
  tranches: Tranche[];
  orders: OrderView[];
  executeFlashing?: boolean;
  moveToBeFlashing?: boolean;
  flattenFlashing?: boolean;
  onStopModeChange: (value: number) => void;
  onStopModeValueChange: (index: number, value: StopMode) => void;
  onExecute: () => void;
  onMoveToBe: () => void;
  onFlatten: () => void;
};

export function StopProtectionPanel(props: Props) {
  const {
    setup,
    stopMode,
    stopModes,
    tranches,
    orders,
    executeFlashing = false,
    moveToBeFlashing = false,
    flattenFlashing = false,
    onStopModeChange,
    onStopModeValueChange,
    onExecute,
    onMoveToBe,
    onFlatten
  } = props;
  const rows = stopPlanRows(setup, tranches, stopMode, stopModes, orders);
  const hasSetup = Boolean(setup);
  const hasTrade = tranches.length > 0;
  const stopModeLabel = !hasSetup
    ? ""
    : !hasTrade
      ? "NOT SET"
      : stopMode === 1
        ? "S1"
        : stopMode === 2
          ? "S1\u00B7S2"
          : "S1\u00B7S2\u00B7S3";

  return (
    <div className="panel protect-panel">
      <div className="panel-header protect-header">
        <div className="panel-title">Stop Protection</div>
        <div className="protect-controls">
          <span className="protect-caption">STOPS</span>
          <button type="button" className={`tranche-count-btn ${stopMode === 1 ? "active" : ""}`} disabled={!hasTrade} onClick={() => onStopModeChange(1)}>S1</button>
          <button type="button" className={`tranche-count-btn ${stopMode === 2 ? "active" : ""}`} disabled={!hasTrade} onClick={() => onStopModeChange(2)}>S1{"\u00B7"}S2</button>
          <button type="button" className={`tranche-count-btn ${stopMode === 3 ? "active" : ""}`} disabled={!hasTrade} onClick={() => onStopModeChange(3)}>S1{"\u00B7"}S2{"\u00B7"}S3</button>
          <button type="button" className={`stop-ok-btn ${hasTrade ? "stop-ok-ready" : ""} ${executeFlashing ? "flash" : ""}`} disabled={!hasTrade} onClick={onExecute}>EXECUTE</button>
          <div className="stop-mode-label">{stopModeLabel}</div>
        </div>
      </div>
      <div className="stop-plan-shell">
        <div className="section-label stop-plan-title">
          Stop Plan <span className="section-hint">{hasTrade ? "" : hasSetup ? "\u2014 Enter trade first" : ""}</span>
        </div>
        <div className="stop-plan-content">
          {!hasSetup ? null : rows.map((row, index) => {
            const mode = stopModes[index] ?? { mode: "stop", pct: 100 };
            const isBreakeven = mode.mode === "be";
            const statusClass = row.status === "ACTIVE"
              ? "plan-status-live"
              : row.status === "MODIFIED"
                ? "plan-status-modified"
                : row.status === "CANCELED"
                  ? "plan-status-canceled"
                  : "plan-status-preview";
            return (
              <div className="plan-line" key={row.label}>
                <span className="plan-line-label">{row.label}</span>
                <button
                  type="button"
                  className={`mode-toggle ${isBreakeven ? "runner" : "limit"}`}
                  onClick={() => onStopModeValueChange(index, { ...mode, mode: isBreakeven ? "stop" : "be" })}
                >
                  {isBreakeven ? "BE" : "STOP"}
                </button>
                <div className="pct-input-wrap">
                  <input
                    type="number"
                    inputMode="decimal"
                    className="pct-input"
                    value={Number((mode.pct ?? row.pct).toFixed(2))}
                    disabled={isBreakeven}
                    onChange={(event) => onStopModeValueChange(index, { ...mode, pct: Number(event.target.value) })}
                  />
                  <span className="pct-suffix">%</span>
                </div>
                <span className="plan-price">{fp(row.price)}</span>
                <span className="plan-qty">{row.qty} sh</span>
                <div className="plan-coverage">
                  {row.coveredTranches.map((trancheId) => (
                    <span className="plan-coverage-pill" key={`${row.label}-${trancheId}`}>{trancheId}</span>
                  ))}
                </div>
                <span className={`plan-status ${statusClass}`}>{row.status}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="panel-body protect-actions">
        <button type="button" className={`btn btn-ghost ${moveToBeFlashing ? "flash" : ""}`} disabled={!hasTrade} onClick={onMoveToBe}>ALL {"\u2192"} BE</button>
        <button type="button" className={`btn btn-red ${flattenFlashing ? "flash" : ""}`} disabled={!hasTrade} onClick={onFlatten}>{"\u2B1B"} FLATTEN</button>
      </div>
    </div>
  );
}
