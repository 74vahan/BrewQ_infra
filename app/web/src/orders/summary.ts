import { ORDER_STATUSES } from '../api/types.ts';
import type { BaristaOrder, OrderStatus } from '../api/types.ts';

export interface StatusCount {
  status: OrderStatus;
  count: number;
}

/** How many of today's orders are in each status, in workflow order; empty statuses are left out. */
export function countByStatus(orders: readonly BaristaOrder[]): StatusCount[] {
  return ORDER_STATUSES.map((status) => ({
    status,
    count: orders.filter((order) => order.status === status).length,
  })).filter(({ count }) => count > 0);
}
