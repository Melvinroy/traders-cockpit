"use client";

import { OrdersBlotter } from "@/components/OrdersBlotter";
import type { OrderView } from "@/lib/types";

type Props = {
  orders: OrderView[];
  activeSymbol: string;
  cancelingBrokerOrderId?: string | null;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onCancelOrder: (brokerOrderId: string) => void;
};

export function RecentOrdersPanel({
  orders,
  activeSymbol,
  cancelingBrokerOrderId = null,
  collapsed = false,
  onToggleCollapse,
  onCancelOrder,
}: Props) {
  return (
    <div className={`panel orders-monitor-panel ${collapsed ? "panel-collapsed" : ""}`}>
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
          <div className="panel-title">Recent Orders</div>
        </div>
      </div>
      {!collapsed ? (
        <div className="panel-body orders-monitor-body">
          <OrdersBlotter
            orders={orders}
            activeSymbol={activeSymbol}
            cancelingBrokerOrderId={cancelingBrokerOrderId}
            onCancel={onCancelOrder}
          />
        </div>
      ) : null}
    </div>
  );
}
