"use client";

import { OpenPositionsList } from "@/components/OpenPositionsList";
import type { PositionView } from "@/lib/types";

type Props = {
  positions: PositionView[];
  activeSymbol: string;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onSelectPosition: (symbol: string) => void;
};

export function OpenPositionsPanel({
  positions,
  activeSymbol,
  collapsed = false,
  onToggleCollapse,
  onSelectPosition,
}: Props) {
  const openCount = positions.filter((position) =>
    ["entry_filled", "protected", "P1_done", "P2_done", "runner_only"].includes(position.phase),
  ).length;

  return (
    <div className={`panel open-positions-panel ${collapsed ? "panel-collapsed" : ""}`}>
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
          <div className="panel-title">Open Positions</div>
        </div>
        <div className="panel-symbol op-header-meta">
          <span className="op-header-count">{openCount}</span>
          <span className="op-header-live">LIVE</span>
        </div>
      </div>
      {!collapsed ? (
        <div className="panel-body open-positions-body">
          <OpenPositionsList positions={positions} activeSymbol={activeSymbol} onSelect={onSelectPosition} />
        </div>
      ) : null}
    </div>
  );
}
