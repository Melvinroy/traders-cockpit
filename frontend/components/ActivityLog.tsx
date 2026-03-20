import type { LogEntry } from "@/lib/types";
import { formatLogTime } from "@/lib/cockpit-ui";

export function ActivityLog({ logs, onClear }: { logs: LogEntry[]; onClear: () => void }) {
  return (
    <div className="panel log-panel">
      <div className="panel-header">
        <div className="panel-title">Activity Log</div>
        <button type="button" className="btn btn-ghost log-clear-btn" onClick={onClear}>CLR</button>
      </div>
      <div className="log-body">
        {logs.length ? (
          logs.map((entry) => (
            <div className="log-entry" key={entry.id}>
              <div className="log-time">{formatLogTime(entry.created_at)}</div>
              <div className="log-msg">
                <span className={`tag tag-${entry.tag}`}>{entry.tag.toUpperCase()}</span>
                {entry.message}
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state">
            <div className="empty-icon">{"\u2022"}</div>
            No activity yet
          </div>
        )}
      </div>
    </div>
  );
}
