import { fp, sessionStateLabel } from "@/lib/cockpit-ui";
import type { OffHoursMode, SetupResponse } from "@/lib/types";

type Props = {
  setup: SetupResponse | null;
  entryPrice: number;
  stopRef: "lod" | "atr" | "manual";
  manualStop: number | null;
  offHoursMode: OffHoursMode;
  previewFlashing?: boolean;
  enterFlashing?: boolean;
  onEntryChange: (value: number) => void;
  onStopRefChange: (value: "lod" | "atr" | "manual") => void;
  onManualStopChange: (value: number | null) => void;
  onOffHoursModeChange: (value: OffHoursMode) => void;
  onPreview: () => void;
  onEnterTrade: () => void;
};

export function EntryPanel(props: Props) {
  const {
    setup,
    entryPrice,
    stopRef,
    manualStop,
    offHoursMode,
    previewFlashing = false,
    enterFlashing = false,
    onEntryChange,
    onStopRefChange,
    onManualStopChange,
    onOffHoursModeChange,
    onPreview,
    onEnterTrade
  } = props;
  const stopPrice = stopRef === "manual" ? manualStop : stopRef === "atr" ? setup?.atrStop ?? null : setup?.lodStop ?? null;
  const isOffHours = Boolean(setup && setup.sessionState !== "regular_open");

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
                  <button type="button" className={`tranche-count-btn ${stopRef === "lod" ? "active" : ""}`} onClick={() => onStopRefChange("lod")} disabled={!setup?.lodIsValid}>LoD</button>
                  <button type="button" className={`tranche-count-btn ${stopRef === "atr" ? "active" : ""}`} onClick={() => onStopRefChange("atr")} disabled={!setup?.atrIsValid}>ATR</button>
                  <button type="button" className={`tranche-count-btn ${stopRef === "manual" ? "active" : ""}`} onClick={() => onStopRefChange("manual")}>Manual</button>
                </div>
                <div className="manual-stop-wrap">
                  <span className="manual-stop-prefix">$</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    value={manualStop ?? ""}
                    className="manual-stop-input"
                    onChange={(event) => onManualStopChange(event.target.value === "" ? null : Number(event.target.value))}
                    disabled={stopRef !== "manual"}
                  />
                </div>
                <span className="hero-stop-price">{fp(stopPrice)}</span>
              </div>
            </div>
            {setup.manualStopWarning ? <div className="offhours-copy">{setup.manualStopWarning}</div> : null}
            {setup ? (
              <div className="offhours-copy">
                Active stop source: {stopRef === "lod" ? `LoD ${fp(setup.lodStop)}` : stopRef === "atr" ? `ATR ${fp(setup.atrStop)}` : manualStop !== null ? `Manual ${fp(manualStop)}` : "Manual required"}
              </div>
            ) : null}
            <div className="entry-actions-row">
              <button type="button" className={`btn btn-ghost ${previewFlashing ? "flash" : ""}`} onClick={onPreview}>PREVIEW</button>
              <button type="button" className={`btn btn-cyan ${enterFlashing ? "flash" : ""}`} onClick={onEnterTrade}>{"\u2197"} ENTER TRADE</button>
            </div>
            {isOffHours ? (
              <div className="offhours-box">
                <div className="offhours-eyebrow">Alpaca Off-Hours Entry</div>
                <div className="offhours-copy">
                  Session: {sessionStateLabel(setup.sessionState)}. Standard market orders queue for the next regular
                  session. Extended-hours submission is limit-only and uses the current entry price.
                </div>
                <div className="offhours-toggle-group">
                  <button
                    type="button"
                    className={`tranche-count-btn ${offHoursMode === "queue_for_open" ? "active" : ""}`}
                    onClick={() => onOffHoursModeChange("queue_for_open")}
                  >
                    Queue For Open
                  </button>
                  <button
                    type="button"
                    className={`tranche-count-btn ${offHoursMode === "extended_hours_limit" ? "active" : ""}`}
                    onClick={() => onOffHoursModeChange("extended_hours_limit")}
                  >
                    Submit Extended-Hours Limit
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
