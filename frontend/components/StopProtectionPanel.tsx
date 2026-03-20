import type { StopMode, Tranche } from "@/lib/types";

type Props = {
  stopMode: number;
  stopModes: StopMode[];
  tranches: Tranche[];
  onStopModeChange: (value: number) => void;
  onStopModeValueChange: (index: number, value: StopMode) => void;
  onExecute: () => void;
  onMoveToBe: () => void;
  onFlatten: () => void;
};

export function StopProtectionPanel(props: Props) {
  const { stopMode, stopModes, tranches, onStopModeChange, onStopModeValueChange, onExecute, onMoveToBe, onFlatten } = props;
  return (
    <div className="panel protect-panel">
      <div className="panel-header">
        <div className="panel-title">Stop Protection</div>
        <div className="segmented tight">
          <button className={`tranche-count-btn ${stopMode === 1 ? "active" : ""}`} onClick={() => onStopModeChange(1)}>S1</button>
          <button className={`tranche-count-btn ${stopMode === 2 ? "active" : ""}`} onClick={() => onStopModeChange(2)}>S1·S2</button>
          <button className={`tranche-count-btn ${stopMode === 3 ? "active" : ""}`} onClick={() => onStopModeChange(3)}>S1·S2·S3</button>
          <button className="btn btn-amber" onClick={onExecute}>EXECUTE</button>
        </div>
      </div>
      <div className="panel-body">
        {(tranches.length ? stopModes.slice(0, stopMode || 3) : []).map((mode, index) => (
          <div key={`stop-${index}`} className="plan-row">
            <span className="plan-label">S{index + 1}</span>
            <button className={`mode-toggle ${mode.mode === "be" ? "runner" : "limit"}`} onClick={() => onStopModeValueChange(index, { ...mode, mode: mode.mode === "stop" ? "be" : "stop" })}>
              {mode.mode === "be" ? "BE" : "STOP"}
            </button>
            <input
              className="plan-input"
              type="number"
              value={mode.pct ?? 100}
              onChange={(event) => onStopModeValueChange(index, { ...mode, pct: Number(event.target.value) })}
              disabled={mode.mode === "be"}
            />
            <span className="plan-hint">{tranches[index]?.qty ?? 0} sh</span>
          </div>
        ))}
        <div className="inline-actions">
          <button className="btn btn-ghost" onClick={onMoveToBe}>ALL → BE</button>
          <button className="btn btn-red" onClick={onFlatten}>FLATTEN</button>
        </div>
      </div>
    </div>
  );
}
