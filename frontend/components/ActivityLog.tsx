import type { LogEntry } from "@/lib/types";
import { formatLogTime } from "@/lib/cockpit-ui";

export function ActivityLog({
  logs,
  onClear,
  clearFlashing = false,
  collapsed = false,
  onToggleCollapse,
}: {
  logs: LogEntry[];
  onClear: () => void;
  clearFlashing?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  const visibleLogs = logs.slice(0, 60);

  return (
    <div className={`panel log-panel ${collapsed ? "panel-collapsed" : ""}`}>
      <div className="panel-header">
        <div className="panel-title-row panel-title-row-clickable" onClick={onToggleCollapse}>
          <button
            type="button"
            className="panel-collapse-btn"
            onClick={(event) => {
              event.stopPropagation();
              onToggleCollapse?.();
            }}
          >
            {collapsed ? "+" : "-"}
          </button>
          <div className="panel-title">Activity Log</div>
        </div>
        <button type="button" className={`btn btn-ghost log-clear-btn ${clearFlashing ? "flash" : ""}`} onClick={onClear} disabled={collapsed}>
          CLR
        </button>
      </div>
      {!collapsed ? (
        <div className="log-body">
          {visibleLogs.length ? (
            visibleLogs.map((entry) => (
              <div className="log-entry" key={entry.id}>
                <div className="log-time">{formatLogTime(entry.created_at)}</div>
                <div className="log-msg">
                  <span className={`tag tag-${entry.tag}`}>{entry.tag.toUpperCase()}</span>
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
      ) : null}
    </div>
  );
}
