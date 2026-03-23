import { fp } from "@/lib/cockpit-ui";
import { firstEntryOrderIssue, type EntryOrderIssue } from "@/lib/entry-order-rules";
import type { EntryOrderDraft, EntryOrderType, EntrySide, OtoExitSide, OrderClass, SetupResponse, TimeInForce } from "@/lib/types";

const ORDER_TYPE_OPTIONS: Array<{ value: EntryOrderType; label: string }> = [
  { value: "limit", label: "LIMIT" },
  { value: "market", label: "MARKET" },
  { value: "stop", label: "STOP" },
  { value: "stop_limit", label: "STOP LIMIT" },
];

const ORDER_CLASS_OPTIONS: Array<{ value: OrderClass; label: string }> = [
  { value: "simple", label: "SIMPLE" },
  { value: "bracket", label: "BRACKET" },
  { value: "oto", label: "OTO" },
  { value: "oco", label: "OCO" },
];

const TIF_OPTIONS: Array<{ value: TimeInForce; label: string }> = [
  { value: "day", label: "DAY" },
  { value: "gtc", label: "GTC" },
  { value: "ioc", label: "IOC" },
  { value: "fok", label: "FOK" },
  { value: "opg", label: "OPG" },
  { value: "cls", label: "CLS" },
];

const SIDE_OPTIONS: Array<{ value: EntrySide; label: string }> = [
  { value: "buy", label: "BUY" },
  { value: "sell", label: "SELL" },
];

type Props = {
  ticker: string;
  setupLoadPending: boolean;
  onTickerChange: (value: string) => void;
  onLoad: () => void;
  setup: SetupResponse | null;
  activeSymbolLabel: string;
  livePrice: number | null;
  delta: number;
  deltaPct: number;
  entryPrice: number;
  stopRef: "lod" | "atr" | "manual";
  manualStop: number | null;
  displayStopPrice: number | null;
  order: EntryOrderDraft;
  orderIssues?: EntryOrderIssue[];
  attachedSummary: { takeProfit: number | null; stopLoss: number | null };
  actionsDisabled?: boolean;
  disabledReason?: string | null;
  previewFlashing?: boolean;
  enterFlashing?: boolean;
  onEntryChange: (value: number) => void;
  onStopRefChange: (value: "lod" | "atr" | "manual") => void;
  onManualStopChange: (value: number | null) => void;
  onOrderChange: (value: EntryOrderDraft) => void;
  onPreview: () => void;
  onEnterTrade: () => void;
};

export function EntryPanel(props: Props) {
  const {
    ticker,
    setupLoadPending,
    onTickerChange,
    onLoad,
    setup,
    activeSymbolLabel,
    livePrice,
    delta,
    deltaPct,
    entryPrice,
    stopRef,
    manualStop,
    displayStopPrice,
    order,
    orderIssues = [],
    attachedSummary,
    actionsDisabled = false,
    disabledReason = null,
    previewFlashing = false,
    enterFlashing = false,
    onEntryChange,
    onStopRefChange,
    onManualStopChange,
    onOrderChange,
    onPreview,
    onEnterTrade,
  } = props;

  const stopPrice = displayStopPrice;
  const cycleStopRef = () => {
    if (!setup) return;
    const lodLikeValid = order.side === "sell" ? setup.hod > entryPrice : setup.lodStop < entryPrice;
    const atrLikePrice = order.side === "sell"
      ? Number((entryPrice + setup.atr14).toFixed(2))
      : Number((entryPrice - setup.atr14).toFixed(2));
    const atrLikeValid = atrLikePrice > 0 && (order.side === "sell" ? atrLikePrice > entryPrice : atrLikePrice < entryPrice);
    const availableRefs: Array<"lod" | "atr" | "manual"> = [
      ...(lodLikeValid ? ["lod" as const] : []),
      ...(atrLikeValid ? ["atr" as const] : []),
      "manual",
    ];
    const currentIndex = availableRefs.indexOf(stopRef);
    const nextRef = availableRefs[(currentIndex + 1 + availableRefs.length) % availableRefs.length] ?? "manual";
    onStopRefChange(nextRef);
  };
  const stopRefLabel = stopRef === "lod" ? (order.side === "sell" ? "HoD" : "LoD") : stopRef === "atr" ? "ATR" : "Manual";
  const showLimitInput = order.orderType === "limit" || order.orderType === "stop_limit";
  const showTriggerInput = order.orderType === "stop" || order.orderType === "stop_limit";
  const showAttachedSummary = order.orderClass !== "simple";
  const entryFieldLabel = "Indicative";
  const limitFieldLabel = "Order Price";
  const triggerFieldLabel = "Trigger";
  const typeIssue = firstEntryOrderIssue(orderIssues, "orderType");
  const tifIssue = firstEntryOrderIssue(orderIssues, "timeInForce");
  const classIssue = firstEntryOrderIssue(orderIssues, "orderClass");
  const limitIssue = firstEntryOrderIssue(orderIssues, "limitPrice");
  const triggerIssue = firstEntryOrderIssue(orderIssues, "stopPrice");
  const inlineIssues = orderIssues.filter((issue, index, all) =>
    all.findIndex((candidate) => candidate.message === issue.message && candidate.severity === issue.severity) === index
  );

  return (
    <div className="panel entry-panel">
      <div className="panel-header entry-panel-header">
        <div className="panel-title">Trade Entry</div>
        <div className="entry-header-market" style={{ display: setup ? "flex" : "none" }}>
          <div className="entry-live-price" style={{ display: livePrice === null ? "none" : "flex" }}>
            <span className="entry-live-symbol">{activeSymbolLabel}</span>
            <span>{fp(livePrice)}</span>
            <span className={`change ${delta >= 0 ? "up" : "dn"}`}>
              {delta >= 0 ? "+" : ""}
              {fp(delta)} ({deltaPct >= 0 ? "+" : ""}
              {deltaPct.toFixed(2)}%)
            </span>
          </div>
          {setup ? (
            <>
              <div className="entry-quote-item">
                <span className="entry-quote-label">Suggested Entry</span>
                <span className="entry-quote-value cyan">{fp(setup.entry)}</span>
              </div>
              <div className="entry-quote-item">
                <span className="entry-quote-label">Bid / Ask</span>
                <span className="entry-quote-value">{fp(setup.bid)} / {fp(setup.ask)}</span>
              </div>
              <div className="entry-quote-item">
                <span className="entry-quote-label">Last</span>
                <span className="entry-quote-value">{fp(setup.last)}</span>
              </div>
            </>
          ) : null}
        </div>
      </div>
      <div className="panel-body entry-body">
        <div className="entry-stack">
          <div className="entry-order-strip">
            <div className="ticker-input-wrap entry-ticker-wrap">
              <div className="ticker-prefix">$</div>
              <input
                id="tickerInput"
                value={ticker}
                onChange={(event) => onTickerChange(event.target.value.toUpperCase())}
                onKeyDown={(event) => event.key === "Enter" && onLoad()}
                placeholder="AAPL"
                maxLength={6}
                autoComplete="off"
              />
            </div>
            {setupLoadPending ? <div className="ticker-loading">SYNCING</div> : null}
            <div className="entry-order-field">
              <span className="entry-order-label">Side</span>
              <div className="entry-side-toggle" role="group" aria-label="Entry side">
                {SIDE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={`entry-side-btn ${order.side === option.value ? "active" : ""}`}
                    onClick={() => onOrderChange({ ...order, side: option.value })}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="entry-order-field">
              <span className="entry-order-label">{entryFieldLabel}</span>
              <input
                id="heroEntry"
                type="number"
                inputMode="decimal"
                value={entryPrice}
                className="entry-order-input"
                onChange={(event) => onEntryChange(Number(event.target.value))}
              />
              <div className="entry-order-copy">
                Active stop:{" "}
                {setup
                  ? stopRef === "lod"
                    ? `${order.side === "sell" ? "HoD" : "LoD"} ${fp(order.side === "sell" ? setup.hod : setup.lodStop)}`
                    : stopRef === "atr"
                      ? `ATR ${fp(stopPrice)}`
                      : manualStop !== null
                        ? `Manual ${fp(manualStop)}`
                        : "Manual required"
                  : "Load setup"}
              </div>
            </div>
            <div className={`entry-order-field ${typeIssue ? "entry-order-field-invalid" : ""}`}>
              <span className="entry-order-label">Type</span>
              <select
                className="entry-select"
                aria-invalid={Boolean(typeIssue)}
                title={typeIssue ?? undefined}
                value={order.orderType}
                onChange={(event) => onOrderChange({ ...order, orderType: event.target.value as EntryOrderType })}
              >
                {ORDER_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className={`entry-order-field ${tifIssue ? "entry-order-field-invalid" : ""}`}>
              <span className="entry-order-label">TIF</span>
              <select
                className="entry-select"
                aria-invalid={Boolean(tifIssue)}
                title={tifIssue ?? undefined}
                value={order.timeInForce}
                onChange={(event) => onOrderChange({ ...order, timeInForce: event.target.value as TimeInForce })}
              >
                {TIF_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className={`entry-order-field ${classIssue ? "entry-order-field-invalid" : ""}`}>
              <span className="entry-order-label">Class</span>
              <select
                className="entry-select"
                aria-invalid={Boolean(classIssue)}
                title={classIssue ?? undefined}
                value={order.orderClass}
                onChange={(event) => onOrderChange({ ...order, orderClass: event.target.value as OrderClass })}
              >
                {ORDER_CLASS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            {showLimitInput ? (
              <div className={`entry-order-field ${limitIssue ? "entry-order-field-invalid" : ""}`}>
                <span className="entry-order-label">{limitFieldLabel}</span>
                <input
                  type="number"
                  inputMode="decimal"
                  value={order.limitPrice ?? ""}
                  className="entry-order-input"
                  aria-invalid={Boolean(limitIssue)}
                  title={limitIssue ?? undefined}
                  onChange={(event) =>
                    onOrderChange({
                      ...order,
                      limitPrice: event.target.value === "" ? null : Number(event.target.value),
                    })
                  }
                />
              </div>
            ) : null}
            {showTriggerInput ? (
              <div className={`entry-order-field ${triggerIssue ? "entry-order-field-invalid" : ""}`}>
                <span className="entry-order-label">{triggerFieldLabel}</span>
                <input
                  type="number"
                  inputMode="decimal"
                  value={order.stopPrice ?? ""}
                  className="entry-order-input"
                  aria-invalid={Boolean(triggerIssue)}
                  title={triggerIssue ?? undefined}
                  onChange={(event) =>
                    onOrderChange({
                      ...order,
                      stopPrice: event.target.value === "" ? null : Number(event.target.value),
                    })
                  }
                />
              </div>
            ) : null}
            <div className="entry-order-field">
              <span className="entry-order-label">Stop Ref</span>
              <button type="button" className={`stop-ref-cycle stop-ref-cycle-${stopRef}`} onClick={cycleStopRef}>
                {stopRefLabel}
              </button>
            </div>
          </div>
          {!setup ? (
            <div className="entry-empty">Load a setup to enable entry actions.</div>
          ) : (
            <>
              <div className="entry-row entry-row-labels">
                <div className="entry-caption">Shares</div>
                <div className="entry-caption">Protective Stop</div>
                <div className="entry-caption">Attached Exits</div>
              </div>
              <div className="entry-row entry-row-compact">
                <div className="hero-shares">{setup.shares}</div>
                <div className="stop-ref-wrap">
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
                <div className="entry-attach-summary">
                  {showAttachedSummary ? (
                    <>
                      {attachedSummary.takeProfit !== null ? <span>TP {fp(attachedSummary.takeProfit)}</span> : null}
                      {attachedSummary.stopLoss !== null ? <span>SL {fp(attachedSummary.stopLoss)}</span> : null}
                      {order.orderClass === "oto" ? (
                        <select
                          className="entry-select entry-select-oto"
                          value={order.otoExitSide}
                          onChange={(event) => onOrderChange({ ...order, otoExitSide: event.target.value as OtoExitSide })}
                        >
                          <option value="stop_loss">OTO STOP</option>
                          <option value="take_profit">OTO PROFIT</option>
                        </select>
                      ) : null}
                    </>
                  ) : (
                    <span className="entry-attach-empty">Separate stop/profit panels active</span>
                  )}
                </div>
              </div>
              {setup.manualStopWarning ? <div className="offhours-copy">{setup.manualStopWarning}</div> : null}
              {setup.sizingWarning ? <div className="offhours-copy">{setup.sizingWarning}</div> : null}
              {inlineIssues.map((issue) => (
                <div
                  key={`${issue.field}-${issue.severity}-${issue.message}`}
                  className={`offhours-copy ${issue.severity === "error" ? "entry-rule-error" : "entry-rule-note"}`}
                >
                  {issue.message}
                </div>
              ))}
              {disabledReason ? <div className="offhours-copy">{disabledReason}</div> : null}
              <div className="entry-actions-row">
                <button type="button" className={`btn btn-ghost ${previewFlashing ? "flash" : ""}`} onClick={onPreview} disabled={actionsDisabled}>PREVIEW</button>
                <button type="button" className={`btn btn-cyan ${enterFlashing ? "flash" : ""}`} onClick={onEnterTrade} disabled={actionsDisabled}>{"\u2197"} ENTER TRADE</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
