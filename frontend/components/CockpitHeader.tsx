import type { AccountView } from "@/lib/types";

type Props = {
  ticker: string;
  onTickerChange: (value: string) => void;
  onLoad: () => void;
  onReset: () => void;
  phase: string;
  livePrice: number | null;
  delta: number;
  deltaPct: number;
  account: AccountView | null;
};

export function CockpitHeader(props: Props) {
  const { ticker, onTickerChange, onLoad, onReset, phase, livePrice, delta, deltaPct, account } = props;
  return (
    <div className="header">
      <div className="logo">
        TRADER&apos;S <span>/ COCKPIT</span>
      </div>
      <div className="divider-v" />
      <div className="ticker-bar">
        <div className="ticker-input-wrap">
          <div className="ticker-prefix">$</div>
          <input
            id="tickerInput"
            value={ticker}
            onChange={(event) => onTickerChange(event.target.value.toUpperCase())}
            onKeyDown={(event) => event.key === "Enter" && onLoad()}
            placeholder="AAPL"
            maxLength={6}
          />
        </div>
        <button className="btn btn-cyan" onClick={onLoad}>
          LOAD SETUP
        </button>
        <button className="btn btn-ghost" onClick={onReset}>
          RESET
        </button>
      </div>
      <div className="badge badge-paper">{account?.mode?.includes("live") ? "LIVE" : "PAPER"}</div>
      <div className={`state-display state-${phase.replace(/\s+/g, "_")}`}>{phase.replaceAll("_", " ").toUpperCase()}</div>
      <div className="live-price">
        {ticker ? `${ticker} ${livePrice?.toFixed(2) ?? "0.00"}` : ""}
        {ticker ? (
          <span className={`change ${delta >= 0 ? "up" : "dn"}`}>
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(2)} ({deltaPct >= 0 ? "+" : ""}
            {deltaPct.toFixed(2)}%)
          </span>
        ) : null}
      </div>
    </div>
  );
}
