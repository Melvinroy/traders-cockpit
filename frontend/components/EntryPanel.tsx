import { fp } from "@/lib/cockpit-ui";
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
  const stopPrice = stopRef === "manual" ? manualStop : setup?.finalStop ?? 0;

  return (
    <div className="panel entry-panel">
      <div className="panel-header"><div className="panel-title">Trade Entry</div></div>
      <div className="panel-body entry-body">
        {!setup ? (
          <div className="entry-empty">Load a setup to enable entry actions.</div>
        ) : (
          <div className="entry-stack">
            <div className="entry-row entry-row-labels">
              <div className="entry-caption">Entry Price</div>
              <div className="entry-caption">Shares to Buy</div>
              <div className="entry-spacer" />
              <div className="entry-caption">Stop Reference</div>
            </div>
            <div className="entry-row entry-row-main">
              <input
                id="heroEntry"
                type="number"
                inputMode="decimal"
                value={entryPrice}
                className="hero-entry"
                onChange={(event) => onEntryChange(Number(event.target.value))}
              />
              <div className="hero-shares">{setup.shares}</div>
              <div className="entry-v-divider" />
              <div className="stop-ref-wrap">
                <div className="entry-toggle-group">
                  <button type="button" className={`tranche-count-btn ${stopRef === "lod" ? "active" : ""}`} onClick={() => onStopRefChange("lod")}>LoD</button>
                  <button type="button" className={`tranche-count-btn ${stopRef === "atr" ? "active" : ""}`} onClick={() => onStopRefChange("atr")}>ATR</button>
                  <button type="button" className={`tranche-count-btn ${stopRef === "manual" ? "active" : ""}`} onClick={() => onStopRefChange("manual")}>Manual</button>
                </div>
                <div className="manual-stop-wrap">
                  <span className="manual-stop-prefix">$</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    value={manualStop}
                    className="manual-stop-input"
                    onChange={(event) => onManualStopChange(Number(event.target.value))}
                    disabled={stopRef !== "manual"}
                  />
                </div>
                <span className="hero-stop-price">{fp(stopPrice)}</span>
              </div>
            </div>
            <div className="entry-actions-row">
              <button type="button" className="btn btn-ghost" onClick={onPreview}>PREVIEW</button>
              <button type="button" className="btn btn-cyan" onClick={onEnterTrade}>{"\u2197"} ENTER TRADE</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
