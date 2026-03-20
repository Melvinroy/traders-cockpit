import type { LogEntry } from "@/lib/types";
import { formatLogTime } from "@/lib/cockpit-ui";

export function ActivityLog({ logs, onClear, clearFlashing = false }: { logs: LogEntry[]; onClear: () => void; clearFlashing?: boolean }) {
  return (
    <div className="panel log-panel">
      <div className="panel-header">
        <div className="panel-title">Activity Log</div>
        <button type="button" className={`btn btn-ghost log-clear-btn ${clearFlashing ? "flash" : ""}`} onClick={onClear}>CLR</button>
      </div>
      <div className="log-body">
        {logs.length ? (
          logs.map((entry) => (
            <div className="log-entry" key={entry.id}>
              <div className="log-time">{formatLogTime(entry.created_at)}</div>
              <div className="log-msg">
                <span className={`tag tag-${entry.tag}`}>{entry.tag.toUpperCase()}</span>
                {entry.symbol ? <span className="log-symbol-chip">{entry.symbol}</span> : null}
                {entry.message}
              </div>
            </div>
          ))
        ) : (
          <div className="log-entry">
            <div className="log-time">--:--:--</div>
            <div className="log-msg">
              <span className="tag tag-sys">SYS</span>
              Cockpit initialized. Enter ticker to begin.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
