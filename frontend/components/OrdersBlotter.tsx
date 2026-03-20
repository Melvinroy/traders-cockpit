import type { OrderView } from "@/lib/types";

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
            <td colSpan={6}>No orders yet</td>
          </tr>
        ) : (
          orders.map((order) => (
            <tr key={order.id}>
              <td>{order.id}</td>
              <td>{order.type}</td>
              <td>{order.qty}</td>
              <td>{order.price.toFixed(2)}</td>
              <td className={`order-status-${order.status}`}>{order.status}</td>
              <td>{order.tranche}</td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
