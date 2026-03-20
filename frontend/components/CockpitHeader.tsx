import type { AccountView } from "@/lib/types";
import { fp } from "@/lib/cockpit-ui";

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
            autoComplete="off"
          />
        </div>
        <button type="button" className="btn btn-cyan" onClick={onLoad}>
          {"\u2193"} LOAD SETUP
        </button>
        <button type="button" className="btn btn-ghost" onClick={onReset}>
          RESET
        </button>
      </div>
      <div className="badge badge-paper">{account?.mode?.includes("live") ? "LIVE" : "\u25CF PAPER"}</div>
      <div className={`state-display state-${phase}`}>{phase.replaceAll("_", " ").toUpperCase()}</div>
      <div className="live-price" style={{ display: livePrice === null ? "none" : "block" }}>
        <span>{ticker}</span>
        <span> {fp(livePrice)}</span>
        <span className={`change ${delta >= 0 ? "up" : "dn"}`}>
          {delta >= 0 ? "+" : ""}
          {fp(delta)} ({deltaPct >= 0 ? "+" : ""}
          {deltaPct.toFixed(2)}%)
        </span>
      </div>
    </div>
  );
}
