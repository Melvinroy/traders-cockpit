import type { SetupResponse } from "@/lib/types";

type Props = {
  setup: SetupResponse | null;
  entryPrice: number;
  stopRef: "lod" | "atr" | "manual";
  manualStop: number;
  onEntryChange: (value: number) => void;
  onStopRefChange: (value: "lod" | "atr" | "manual") => void;
  onManualStopChange: (value: number) => void;
  onPreview: () => void;
  onEnterTrade: () => void;
};

export function EntryPanel(props: Props) {
  const { setup, entryPrice, stopRef, manualStop, onEntryChange, onStopRefChange, onManualStopChange, onPreview, onEnterTrade } = props;
  return (
    <div className="panel entry-panel">
      <div className="panel-header">
        <div className="panel-title">Trade Entry</div>
      </div>
      <div className="panel-body">
        {!setup ? (
          <div className="empty-inline">Load a setup to enable entry actions.</div>
        ) : (
          <div className="entry-grid">
            <label className="field">
              <span>Entry Price</span>
              <input type="number" value={Number.isFinite(entryPrice) ? entryPrice : setup.entry} onChange={(event) => onEntryChange(Number(event.target.value))} />
            </label>
            <label className="field">
              <span>Shares to Buy</span>
              <input type="text" readOnly value={setup.shares} />
            </label>
            <div className="field">
              <span>Stop Reference</span>
              <div className="segmented">
                <button className={`tranche-count-btn ${stopRef === "lod" ? "active" : ""}`} onClick={() => onStopRefChange("lod")}>LoD</button>
                <button className={`tranche-count-btn ${stopRef === "atr" ? "active" : ""}`} onClick={() => onStopRefChange("atr")}>ATR</button>
                <button className={`tranche-count-btn ${stopRef === "manual" ? "active" : ""}`} onClick={() => onStopRefChange("manual")}>Manual</button>
              </div>
            </div>
            <label className="field">
              <span>Manual Stop</span>
              <input type="number" value={manualStop} onChange={(event) => onManualStopChange(Number(event.target.value))} disabled={stopRef !== "manual"} />
            </label>
            <div className="entry-actions">
              <button className="btn btn-ghost" onClick={onPreview}>PREVIEW</button>
              <button className="btn btn-cyan" onClick={onEnterTrade}>ENTER TRADE</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
