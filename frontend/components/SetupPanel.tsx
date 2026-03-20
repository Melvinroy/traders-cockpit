import { OpenPositionsList } from "@/components/OpenPositionsList";
import { fp } from "@/lib/cockpit-ui";
import type { AccountView, PositionView, SetupResponse } from "@/lib/types";

type Props = {
  symbol: string;
  setup: SetupResponse | null;
  account: AccountView | null;
  positions: PositionView[];
  onSelectPosition: (symbol: string) => void;
  onRiskPctCommit: (value: number) => void;
};

export function SetupPanel({ symbol, setup, account, positions, onSelectPosition, onRiskPctCommit }: Props) {
  const atrExtension = setup?.atrExtension;
  const rvol = setup?.rvol;
  const extFrom10Ma = setup?.extFrom10Ma;
  const daysToCover = setup?.days_to_cover;
  const atrExtensionText = Number.isFinite(atrExtension) ? `${atrExtension?.toFixed(2)}x` : "--";
  const rvolText = Number.isFinite(rvol) ? `${rvol?.toFixed(1)}x` : "--";
  const extFrom10Text = Number.isFinite(extFrom10Ma) ? `${extFrom10Ma?.toFixed(2)}%` : "--";
  const daysToCoverText = Number.isFinite(daysToCover) ? `${daysToCover?.toFixed(1)}` : "--";
  return (
    <div className="panel setup-panel">
      <div className="panel-header">
        <div className="panel-title">Setup Parameters</div>
        <div className="panel-symbol" id="setupSymbol">
          {setup && symbol ? <span className="ticker-symbol-large">{symbol}</span> : "\u2014"}
        </div>
      </div>
      <div className="panel-body" id="setupBody">
        {!setup ? (
          <div className="empty-state">
            <div className="empty-icon">{"\u22A1"}</div>
            Enter ticker and load setup
          </div>
        ) : (
          <>
            <div className="kv-group">
              <div className="kv-group-label">Quote</div>
              <div className="kv-row"><span className="kv-label">Bid</span><span className="kv-val">{fp(setup.bid)}</span></div>
              <div className="kv-row"><span className="kv-label">Ask</span><span className="kv-val">{fp(setup.ask)}</span></div>
              <div className="kv-row"><span className="kv-label">Suggested Entry</span><span className="kv-val cyan">{fp(setup.entry)}</span></div>
            </div>
            <div className="kv-group">
              <div className="kv-group-label">Stop Levels</div>
              <div className="kv-row"><span className="kv-label">Low of Day</span><span className="kv-val">{fp(setup.lod)}</span></div>
              <div className="kv-row"><span className="kv-label">ATR (14)</span><span className="kv-val amber">{fp(setup.atr14)}</span></div>
              <div className="kv-row"><span className="kv-label">Final Stop</span><span className="kv-val red">{fp(setup.finalStop)}</span></div>
            </div>
            <div className="kv-group">
              <div className="kv-group-label">Risk Sizing</div>
              <div className="kv-row"><span className="kv-label">Account Equity</span><span className="kv-val">{fp(account?.equity ?? setup.accountEquity)}</span></div>
              <div className="kv-row">
                <span className="kv-label">Risk %</span>
                <input
                  key={`${symbol}-${account?.risk_pct ?? setup.riskPct}`}
                  type="text"
                  inputMode="decimal"
                  className="risk-pct-input"
                  defaultValue={`${(account?.risk_pct ?? setup.riskPct).toFixed(2)}%`}
                  onFocus={(event) => {
                    event.currentTarget.value = String(account?.risk_pct ?? setup.riskPct);
                  }}
                  onBlur={(event) => {
                    const next = Number.parseFloat(event.currentTarget.value) || (account?.risk_pct ?? setup.riskPct);
                    event.currentTarget.value = `${next.toFixed(2)}%`;
                    onRiskPctCommit(next);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.currentTarget.blur();
                    }
                  }}
                />
              </div>
              <div className="kv-row"><span className="kv-label">Dollar Risk</span><span className="kv-val red">{fp(setup.dollarRisk)}</span></div>
              <div className="kv-row"><span className="kv-label">Per-Share Risk</span><span className="kv-val">{fp(setup.perShareRisk)}</span></div>
              <div className="kv-row"><span className="kv-label">Calc. Shares</span><span className="kv-val green">{setup.shares} sh</span></div>
            </div>
            <div className="kv-group">
              <div className="kv-group-label">Reference</div>
              <div className="kv-row"><span className="kv-label">10 SMA</span><span className="kv-val">{fp(setup.sma10)}</span></div>
              <div className="kv-row"><span className="kv-label">50 SMA</span><span className="kv-val">{fp(setup.sma50)}</span></div>
              <div className="kv-row"><span className="kv-label">200 MA</span><span className="kv-val">{fp(setup.sma200)}</span></div>
              <div className="kv-row"><span className="kv-label">ATR Ext from 50MA</span><span className="kv-val">{atrExtensionText}</span></div>
              <div className="kv-row"><span className="kv-label">RVOL</span><span className="kv-val">{rvolText}</span></div>
              <div className="kv-row"><span className="kv-label">Ext from 10 MA</span><span className="kv-val">{extFrom10Text}</span></div>
              <div className="kv-row">
                <span className="kv-label">Days to Cover</span>
                <span className="kv-val">{daysToCoverText} <span className="kv-val-unit">days</span></span>
              </div>
            </div>
          </>
        )}
        <OpenPositionsList positions={positions} activeSymbol={symbol} onSelect={onSelectPosition} />
      </div>
    </div>
  );
}
