import type { LogEntry } from "@/lib/types";

export function ActivityLog({ logs }: { logs: LogEntry[] }) {
  return (
    <div className="panel log-panel">
      <div className="panel-header">
        <div className="panel-title">Activity Log</div>
      </div>
      <div className="log-body">
        {logs.length ? (
          logs.map((entry) => (
            <div className="log-entry" key={entry.id}>
              <div className="log-time">{new Date(entry.created_at).toLocaleTimeString()}</div>
              <div className="log-msg">
                <span className={`tag tag-${entry.tag}`}>{entry.tag.toUpperCase()}</span>
                {entry.message}
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state">No activity yet</div>
        )}
      </div>
    </div>
  );
}
