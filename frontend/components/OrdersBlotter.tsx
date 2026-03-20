import type { OrderView } from "@/lib/types";
import { fp } from "@/lib/cockpit-ui";

export function OrdersBlotter({ orders }: { orders: OrderView[] }) {
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
          orders.map((order) => (
            <tr key={order.id} title={order.brokerOrderId ?? undefined}>
              <td>{order.id}</td>
              <td>{order.type}</td>
              <td>{order.qty}</td>
              <td>{fp(order.price)}</td>
              <td className={`order-status-${order.status}`}>{order.status}</td>
              <td>{order.tranche}</td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
