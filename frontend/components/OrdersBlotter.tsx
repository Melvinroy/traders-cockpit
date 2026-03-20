import type { OrderView } from "@/lib/types";
import { fp } from "@/lib/cockpit-ui";

function typeColorClass(type: string): string {
  if (type === "STOP") return "order-type-stop";
  if (type === "LMT") return "order-type-limit";
  if (type === "MKT") return "order-type-market";
  if (type === "TRAIL") return "order-type-trail";
  return "";
}

export function OrdersBlotter({ orders }: { orders: OrderView[] }) {
  const roots = orders.filter((order) => !order.parentId);
  const childrenOf = (id: string) => orders.filter((order) => order.parentId === id);

  return (
    <table className="orders-table">
      <thead>
        <tr>
          <th>Order ID</th>
          <th>Type</th>
          <th>Qty</th>
          <th>Price</th>
          <th>Status</th>
          <th>Tranche</th>
        </tr>
      </thead>
      <tbody>
        {!orders.length ? (
          <tr>
            <td colSpan={6} className="orders-empty-cell">No orders yet</td>
          </tr>
        ) : (
          roots.flatMap((root) => {
            const children = childrenOf(root.id);
            const rootRow = (
              <tr key={root.id} className={children.length ? "order-root-row order-root-open" : "order-root-row"} title={root.brokerOrderId ?? undefined}>
                <td className="order-id-root">{root.id}</td>
                <td className={typeColorClass(root.type)}>{root.type}</td>
                <td>{root.qty}</td>
                <td>{fp(root.price)}</td>
                <td className={`order-status-${root.status}`}>{root.status}</td>
                <td>{root.tranche}</td>
              </tr>
            );

            const childRows = children.map((child, index) => {
              const isLast = index === children.length - 1;
              return (
                <tr key={child.id} className={`order-child-row ${isLast ? "order-child-last" : ""}`} title={child.brokerOrderId ?? undefined}>
                  <td className="order-id-child">
                    <span className="order-tree-glyph">{isLast ? "\u2514\u2500" : "\u251C\u2500"}</span>
                    <span>{child.id}</span>
                  </td>
                  <td className={typeColorClass(child.type)}>{child.type}</td>
                  <td className={child.qty < child.origQty ? "order-qty-reduced" : ""}>
                    {child.qty}
                    {child.qty < child.origQty ? <span className="order-orig-qty">({child.origQty})</span> : null}
                  </td>
                  <td>{fp(child.price)}</td>
                  <td className={`order-status-${child.status}`}>{child.status}</td>
                  <td>{child.tranche}</td>
                </tr>
              );
            });

            return [rootRow, ...childRows];
          })
        )}
      </tbody>
    </table>
  );
}
