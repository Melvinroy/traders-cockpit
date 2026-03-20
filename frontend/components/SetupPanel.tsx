import type { PositionView, SetupResponse } from "@/lib/types";
import { OpenPositionsList } from "@/components/OpenPositionsList";

type Props = {
  symbol: string;
  setup: SetupResponse | null;
  positions: PositionView[];
  onSelectPosition: (symbol: string) => void;
};

export function SetupPanel({ symbol, setup, positions, onSelectPosition }: Props) {
  return (
    <div className="panel setup-panel">
      <div className="panel-header">
        <div className="panel-title">Setup Parameters</div>
        <div className="panel-symbol">{symbol || "—"}</div>
      </div>
      <div className="panel-body">
        {!setup ? (
          <div className="empty-state">Enter ticker and load setup</div>
        ) : (
          <>
            <section className="kv-group">
              <div className="kv-group-label">Quote</div>
              <div className="kv-row"><span className="kv-label">Bid</span><span className="kv-val">{setup.bid.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">Ask</span><span className="kv-val">{setup.ask.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">Suggested Entry</span><span className="kv-val cyan">{setup.entry.toFixed(2)}</span></div>
            </section>
            <section className="kv-group">
              <div className="kv-group-label">Stop Levels</div>
              <div className="kv-row"><span className="kv-label">Low of Day</span><span className="kv-val red">{setup.lod.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">ATR (14)</span><span className="kv-val amber">{setup.atr14.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">Final Stop</span><span className="kv-val red">{setup.finalStop.toFixed(2)}</span></div>
            </section>
            <section className="kv-group">
              <div className="kv-group-label">Risk Sizing</div>
              <div className="kv-row"><span className="kv-label">Account Equity</span><span className="kv-val">{setup.accountEquity.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">Risk %</span><span className="kv-val">{setup.riskPct.toFixed(2)}%</span></div>
              <div className="kv-row"><span className="kv-label">Dollar Risk</span><span className="kv-val">{setup.dollarRisk.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">Per Share Risk</span><span className="kv-val">{setup.perShareRisk.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">Calculated Shares</span><span className="kv-val green">{setup.shares}</span></div>
            </section>
            <section className="kv-group">
              <div className="kv-group-label">Reference</div>
              <div className="kv-row"><span className="kv-label">SMA 10</span><span className="kv-val">{setup.sma10.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">SMA 50</span><span className="kv-val">{setup.sma50.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">SMA 200</span><span className="kv-val">{setup.sma200.toFixed(2)}</span></div>
              <div className="kv-row"><span className="kv-label">ATR Extension</span><span className="kv-val">{setup.atrExtension.toFixed(2)}x</span></div>
              <div className="kv-row"><span className="kv-label">RVOL</span><span className="kv-val">{setup.rvol.toFixed(2)}x</span></div>
              <div className="kv-row"><span className="kv-label">Ext from 10MA</span><span className="kv-val">{setup.extFrom10Ma.toFixed(2)}%</span></div>
              <div className="kv-row"><span className="kv-label">Days to Cover</span><span className="kv-val">{setup.days_to_cover.toFixed(2)}</span></div>
            </section>
          </>
        )}
        <OpenPositionsList positions={positions} activeSymbol={symbol} onSelect={onSelectPosition} />
      </div>
    </div>
  );
}
