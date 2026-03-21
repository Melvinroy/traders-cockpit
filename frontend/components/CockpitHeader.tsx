import type { AccountView, AuthUser } from "@/lib/types";
import { fp, phaseLabel } from "@/lib/cockpit-ui";

type Props = {
  ticker: string;
  onTickerChange: (value: string) => void;
  onLoad: () => void;
  onReset: () => void;
  loadFlashing?: boolean;
  resetFlashing?: boolean;
  phase: string;
  livePrice: number | null;
  delta: number;
  deltaPct: number;
  account: AccountView | null;
  authUser: AuthUser | null;
  onLogout: () => void;
};

export function CockpitHeader(props: Props) {
  const {
    ticker,
    onTickerChange,
    onLoad,
    onReset,
    loadFlashing = false,
    resetFlashing = false,
    phase,
    livePrice,
    delta,
    deltaPct,
    account,
    authUser,
    onLogout
  } = props;
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
        <button type="button" className={`btn btn-cyan ${loadFlashing ? "flash" : ""}`} onClick={onLoad}>
          {"\u2193"} LOAD SETUP
        </button>
        <button type="button" className={`btn btn-ghost ${resetFlashing ? "flash" : ""}`} onClick={onReset}>
          RESET
        </button>
      </div>
      <div className="badge badge-paper">{account?.effective_mode?.includes("live") ? "LIVE" : "\u25CF PAPER"}</div>
      <div className={`state-display state-${phase}`}>{phaseLabel(phase)}</div>
      {authUser ? (
        <div className="auth-strip">
          <div className="auth-user">
            {authUser.username}
            <span>{authUser.role}</span>
          </div>
          <button type="button" className="btn btn-ghost auth-logout-btn" onClick={onLogout}>
            LOGOUT
          </button>
        </div>
      ) : null}
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
