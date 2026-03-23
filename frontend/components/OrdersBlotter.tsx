"use client";

import { Fragment, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";

import { formatLogTime, fp } from "@/lib/cockpit-ui";
import type { OrderView } from "@/lib/types";

type Scope = "all" | "active" | "open";

type Props = {
  orders: OrderView[];
  activeSymbol: string;
  onCancel: (brokerOrderId: string) => void;
  cancelingBrokerOrderId?: string | null;
};

type OrderNode = {
  key: string;
  root: OrderView;
  children: OrderView[];
};

type ColumnWidths = {
  symbol: number;
  sideType: number;
};

const STORAGE_KEY = "cockpit.orders-cols.v1";
const DEFAULT_WIDTHS: ColumnWidths = {
  symbol: 104,
  sideType: 108,
};

function compactSide(side?: string | null): string {
  const value = (side ?? "").trim().toUpperCase();
  if (value === "BUY" || value === "B") return "BUY";
  if (value === "SELL" || value === "S") return "SELL";
  return value || "-";
}

function normalizeType(type: string): string {
  const value = type.trim().toUpperCase();
  if (value === "MARKET" || value === "MKT") return "MKT";
  if (value === "LIMIT" || value === "LMT") return "LMT";
  if (value === "STOP" || value === "STP") return "STOP";
  if (value === "TRAIL" || value === "TRAILING") return "TRAIL";
  return value;
}

function typeColorClass(type: string): string {
  const value = normalizeType(type);
  if (value === "STOP") return "order-type-stop";
  if (value === "LMT") return "order-type-limit";
  if (value === "MKT") return "order-type-market";
  if (value === "TRAIL") return "order-type-trail";
  return "";
}

function statusClass(status: string): string {
  return `order-status-${status.toUpperCase()}`;
}

function orderTime(order: OrderView): string {
  return formatLogTime(order.updatedAt ?? order.filledAt ?? order.createdAt ?? "");
}

function orderSortTime(order: OrderView): number {
  const value = order.updatedAt ?? order.filledAt ?? order.createdAt ?? "";
  return new Date(value).getTime() || 0;
}

function sanitizeWidths(widths: ColumnWidths): ColumnWidths {
  return {
    symbol: Math.max(88, Math.min(240, widths.symbol)),
    sideType: Math.max(68, Math.min(160, widths.sideType)),
  };
}

function readStoredWidths(): ColumnWidths {
  if (typeof window === "undefined") return DEFAULT_WIDTHS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_WIDTHS;
    return sanitizeWidths({ ...DEFAULT_WIDTHS, ...(JSON.parse(raw) as Partial<ColumnWidths>) });
  } catch {
    return DEFAULT_WIDTHS;
  }
}

function groupOrders(orders: OrderView[]): OrderNode[] {
  const byId = new Map<string, OrderView>();
  const childrenByParent = new Map<string, OrderView[]>();

  for (const order of orders) {
    byId.set(order.id, order);
    if (order.parentId) {
      const bucket = childrenByParent.get(order.parentId) ?? [];
      bucket.push(order);
      childrenByParent.set(order.parentId, bucket);
    }
  }

  const roots: OrderNode[] = [];
  const handled = new Set<string>();

  for (const order of orders) {
    if (order.parentId && byId.has(order.parentId)) continue;
    const keyBase = order.parentId ?? order.id ?? order.brokerOrderId ?? `${order.symbol}-${order.createdAt ?? ""}`;
    const key = `${keyBase}:${order.id}:${order.createdAt ?? ""}`;
    const children = [...(childrenByParent.get(order.id) ?? [])].sort((left, right) => orderSortTime(right) - orderSortTime(left));
    roots.push({ key, root: order, children });
    handled.add(order.id);
    for (const child of children) handled.add(child.id);
  }

  for (const order of orders) {
    if (handled.has(order.id)) continue;
    roots.push({ key: `${order.id}:${order.createdAt ?? ""}`, root: order, children: [] });
  }

  return roots.sort((left, right) => orderSortTime(right.root) - orderSortTime(left.root));
}

function orderMatchesScope(order: OrderView, scope: Scope, activeSymbol: string): boolean {
  if (scope === "active" && activeSymbol) return order.symbol === activeSymbol;
  if (scope === "open") return order.cancelable;
  return true;
}

function renderOrderRow(
  order: OrderView,
  activeSymbol: string,
  cancelingBrokerOrderId: string | null,
  onCancel: (brokerOrderId: string) => void,
  depth: 0 | 1,
) {
  const isActiveSymbol = Boolean(activeSymbol) && order.symbol === activeSymbol;
  const cancelDisabled = !order.cancelable || !order.brokerOrderId || cancelingBrokerOrderId === order.brokerOrderId;
  const compactType = normalizeType(order.type);
  const sideCode = compactSide(order.side);

  return (
    <tr
      key={`${order.brokerOrderId ?? order.id}-${order.updatedAt ?? order.createdAt ?? ""}`}
      className={`${isActiveSymbol ? "order-row-highlight" : ""} ${depth ? "order-child-row" : "order-root-row"}`}
      title={order.brokerOrderId ?? undefined}
    >
      <td className={`${depth ? "order-tree-indent " : ""}order-symbol-cell`}>
        <div className="order-symbol-main">{order.symbol}</div>
        {order.brokerOrderId ? <div className="order-subtext order-subtext-truncate">{order.brokerOrderId}</div> : null}
      </td>
      <td className="order-side-type-cell">
        <div className="order-side-type-main">
          <span className="order-side-code">{sideCode}</span>
          <span className={`order-type-code ${typeColorClass(compactType)}`}>{compactType}</span>
        </div>
      </td>
      <td>
        <div>{order.qty}</div>
        <div className="order-subtext">fill {order.filledQty} / rem {order.remainingQty}</div>
      </td>
      <td>
        <div>{fp(order.price)}</div>
        {order.fillPrice !== null && order.fillPrice !== undefined ? (
          <div className="order-subtext">fill {fp(order.fillPrice)}</div>
        ) : null}
      </td>
      <td className={statusClass(order.status)}>
        <div>{order.status}</div>
        {order.cancelable ? <div className="order-subtext">cancelable</div> : null}
      </td>
      <td>{orderTime(order)}</td>
      <td>
        <div>{order.tranche}</div>
        <div className="order-subtext">{order.parentId ? "child" : "root"}</div>
      </td>
      <td>
        {order.cancelable && order.brokerOrderId ? (
          <button
            type="button"
            className="orders-cancel-btn"
            disabled={cancelDisabled}
            onClick={() => onCancel(order.brokerOrderId!)}
          >
            {cancelingBrokerOrderId === order.brokerOrderId ? "..." : "Cancel"}
          </button>
        ) : (
          <span className="order-subtext">-</span>
        )}
      </td>
    </tr>
  );
}

export function OrdersBlotter({ orders, activeSymbol, onCancel, cancelingBrokerOrderId = null }: Props) {
  const [scope, setScope] = useState<Scope>("all");
  const [expandedRoots, setExpandedRoots] = useState<Record<string, boolean>>({});
  const [columnWidths, setColumnWidths] = useState<ColumnWidths>(DEFAULT_WIDTHS);
  const dragCleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    setColumnWidths(readStoredWidths());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sanitizeWidths(columnWidths)));
  }, [columnWidths]);

  useEffect(() => () => {
    dragCleanupRef.current?.();
  }, []);

  function beginColumnDrag(column: keyof ColumnWidths, event: ReactMouseEvent<HTMLSpanElement>) {
    if (typeof window === "undefined" || window.innerWidth <= 1024) return;
    event.preventDefault();
    event.stopPropagation();
    dragCleanupRef.current?.();
    const startX = event.clientX;
    const start = { ...columnWidths };

    const onMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      setColumnWidths((current) =>
        sanitizeWidths({
          ...current,
          [column]: start[column] + deltaX,
        }),
      );
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      dragCleanupRef.current = null;
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    dragCleanupRef.current = onUp;
  }

  const groupedOrders = useMemo(() => {
    const safeOrders = Array.isArray(orders) ? orders : [];
    return groupOrders(safeOrders)
      .map((node) => {
        const matchingChildren = node.children.filter((order) => orderMatchesScope(order, scope, activeSymbol));
        const rootMatches = orderMatchesScope(node.root, scope, activeSymbol);
        if (!rootMatches && matchingChildren.length === 0) return null;
        return {
          ...node,
          children: matchingChildren,
          rootVisible: rootMatches || matchingChildren.length > 0,
        };
      })
      .filter((node): node is OrderNode & { rootVisible: true } => Boolean(node && node.rootVisible));
  }, [activeSymbol, orders, scope]);

  const totalVisibleRows = groupedOrders.reduce((sum, node) => {
    const expanded = expandedRoots[node.key] ?? false;
    return sum + 1 + (expanded ? node.children.length : 0);
  }, 0);

  return (
    <div className="orders-blotter-shell">
      <div className="orders-toolbar">
        <div className="orders-filters">
          <button type="button" className={`orders-filter-btn ${scope === "all" ? "active" : ""}`} onClick={() => setScope("all")}>
            All
          </button>
          <button
            type="button"
            className={`orders-filter-btn ${scope === "active" ? "active" : ""}`}
            onClick={() => setScope("active")}
            disabled={!activeSymbol}
          >
            Active Symbol
          </button>
          <button type="button" className={`orders-filter-btn ${scope === "open" ? "active" : ""}`} onClick={() => setScope("open")}>
            Open / Working
          </button>
        </div>
        <div className="orders-meta">{totalVisibleRows} visible row{totalVisibleRows === 1 ? "" : "s"}</div>
      </div>
      <table className="orders-table merged-orders-table">
        <colgroup>
          <col className="orders-col-symbol" style={{ width: `${columnWidths.symbol}px` }} />
          <col className="orders-col-side-type" style={{ width: `${columnWidths.sideType}px` }} />
          <col className="orders-col-qty" />
          <col className="orders-col-price" />
          <col className="orders-col-status" />
          <col className="orders-col-time" />
          <col className="orders-col-context" />
          <col className="orders-col-action" />
        </colgroup>
        <thead>
          <tr>
            <th>
              <span className="orders-header-label">Symbol</span>
              <span className="orders-col-resize-handle" onMouseDown={(event) => beginColumnDrag("symbol", event)} />
            </th>
            <th>
              <span className="orders-header-label">Side / Type</span>
              <span className="orders-col-resize-handle" onMouseDown={(event) => beginColumnDrag("sideType", event)} />
            </th>
            <th>Qty</th>
            <th>Price</th>
            <th>Status</th>
            <th>Time</th>
            <th>Context</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {!groupedOrders.length ? (
            <tr>
              <td colSpan={8} className="orders-empty-cell">No recent orders in this view</td>
            </tr>
          ) : (
            groupedOrders.map((node) => {
              const expanded = expandedRoots[node.key] ?? false;
              return (
                <Fragment key={node.key}>
                  {node.children.length ? (
                    <tr className="order-tree-toggle-row">
                      <td colSpan={8}>
                        <button
                          type="button"
                          className="order-tree-toggle"
                          onClick={() =>
                            setExpandedRoots((current) => ({
                              ...current,
                              [node.key]: !expanded,
                            }))
                          }
                        >
                          <span className="order-tree-toggle-main">
                            {expanded ? "-" : "+"} {node.root.symbol} {node.root.tranche} {node.children.length} child order{node.children.length === 1 ? "" : "s"}
                          </span>
                          {node.root.brokerOrderId ? (
                            <span className="order-tree-toggle-meta" title={node.root.brokerOrderId}>
                              {node.root.brokerOrderId}
                            </span>
                          ) : null}
                        </button>
                      </td>
                    </tr>
                  ) : null}
                  {renderOrderRow(node.root, activeSymbol, cancelingBrokerOrderId, onCancel, 0)}
                  {expanded ? node.children.map((order) => renderOrderRow(order, activeSymbol, cancelingBrokerOrderId, onCancel, 1)) : null}
                </Fragment>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
