import { fp, stopPlanRows } from "@/lib/cockpit-ui";
import type { EntrySide, OrderView, SetupResponse, StopMode, Tranche } from "@/lib/types";

type Props = {
  setup: SetupResponse | null;
  phase: string | null;
  entrySide: EntrySide;
  stopMode: number;
  stopModes: StopMode[];
  tranches: Tranche[];
  orders: OrderView[];
  executeFlashing?: boolean;
  moveToBeFlashing?: boolean;
  flattenFlashing?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onStopModeChange: (value: number) => void;
  onStopModeValueChange: (index: number, value: StopMode) => void;
  onExecute: () => void;
  onMoveToBe: () => void;
  onFlatten: () => void;
};

export function StopProtectionPanel(props: Props) {
  const {
    setup,
    phase,
    entrySide,
    stopMode,
    stopModes,
    tranches,
    orders,
    executeFlashing = false,
    moveToBeFlashing = false,
    flattenFlashing = false,
    collapsed = false,
    onToggleCollapse,
    onStopModeChange,
    onStopModeValueChange,
    onExecute,
    onMoveToBe,
    onFlatten
  } = props;
  const rows = stopPlanRows(setup, tranches, stopMode, stopModes, orders, entrySide);
  const hasSetup = Boolean(setup);
  const hasTrade = tranches.length > 0;
  const waitingForFill = phase === "entry_pending";
  const stopModeLabel = !hasSetup
    ? ""
    : !hasTrade
      ? waitingForFill
        ? "WAITING FOR FILL"
        : "NOT SET"
      : stopMode === 1
        ? "S1"
        : stopMode === 2
          ? "S1\u00B7S2"
          : "S1\u00B7S2\u00B7S3";

  return (
    <div className={`panel protect-panel ${collapsed ? "panel-collapsed" : ""}`}>
      <div className="panel-header protect-header">
        <div className="panel-title-row">
          <button type="button" className="panel-collapse-btn" onClick={onToggleCollapse}>{collapsed ? "+" : "-"}</button>
          <div className="panel-title">Stop Protection</div>
        </div>
        <div className="protect-controls">
          <span className="protect-caption">STOPS</span>
          <button type="button" className={`tranche-count-btn ${stopMode === 1 ? "active" : ""}`} disabled={!hasTrade || waitingForFill} onClick={() => onStopModeChange(1)}>S1</button>
          <button type="button" className={`tranche-count-btn ${stopMode === 2 ? "active" : ""}`} disabled={!hasTrade || waitingForFill} onClick={() => onStopModeChange(2)}>S1{"\u00B7"}S2</button>
          <button type="button" className={`tranche-count-btn ${stopMode === 3 ? "active" : ""}`} disabled={!hasTrade || waitingForFill} onClick={() => onStopModeChange(3)}>S1{"\u00B7"}S2{"\u00B7"}S3</button>
          <button type="button" className={`stop-ok-btn ${hasTrade && !waitingForFill ? "stop-ok-ready" : ""} ${executeFlashing ? "flash" : ""}`} disabled={!hasTrade || waitingForFill} onClick={onExecute}>EXECUTE</button>
          <div className="stop-mode-label">{stopModeLabel}</div>
        </div>
      </div>
      {!collapsed ? <>
      <div className="stop-plan-shell">
        <div className="section-label stop-plan-title">
          Stop Plan <span className="section-hint">{waitingForFill ? "— Protective orders are unavailable until the entry order is filled" : hasTrade ? "" : hasSetup ? "— Enter trade first" : ""}</span>
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
                  disabled={waitingForFill}
                >
                  {isBreakeven ? "BE" : "STOP"}
                </button>
                <div className="pct-input-wrap">
                  <input
                    type="number"
                    inputMode="decimal"
                    className="pct-input"
                    value={Number((mode.pct ?? row.pct).toFixed(2))}
                    disabled={isBreakeven || waitingForFill}
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
          {hasSetup ? (
            <div className="plan-line stop-action-line">
              <span className="plan-line-label">ACT</span>
              <div className="stop-action-buttons">
                <button type="button" className={`btn btn-ghost stop-inline-btn ${moveToBeFlashing ? "flash" : ""}`} disabled={!hasTrade || waitingForFill} onClick={onMoveToBe}>ALL {"\u2192"} BE</button>
                <button type="button" className={`btn btn-red stop-inline-btn ${flattenFlashing ? "flash" : ""}`} disabled={!hasTrade} onClick={onFlatten}>{"\u2B1B"} FLATTEN</button>
              </div>
              <span className="stop-action-copy">
                {waitingForFill ? "Awaiting broker fill" : hasTrade ? "Stop actions ready" : "No live trade"}
              </span>
            </div>
          ) : null}
        </div>
      </div>
      </> : null}
    </div>
  );
}
