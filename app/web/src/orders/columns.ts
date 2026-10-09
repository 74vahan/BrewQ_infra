import type { BaristaOrder, OrderStatus } from '../api/types.ts';

/** The three columns of the queue, left to right (the order of the work). */
export const QUEUE_COLUMNS = ['NEW', 'IN_PROGRESS', 'READY'] as const satisfies readonly OrderStatus[];
export type QueueColumn = (typeof QUEUE_COLUMNS)[number];

/**
 * Splits the active orders into the columns, oldest first (the one waiting
 * longest is on top). Orders in a status the queue does not know are left out.
 */
export function groupByStatus(orders: readonly BaristaOrder[]): Record<QueueColumn, BaristaOrder[]> {
  const columns: Record<QueueColumn, BaristaOrder[]> = { NEW: [], IN_PROGRESS: [], READY: [] };
  for (const order of orders) {
    if ((QUEUE_COLUMNS as readonly string[]).includes(order.status)) {
      columns[order.status as QueueColumn].push(order);
    }
  }
  for (const list of Object.values(columns)) {
    list.sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id);
  }
  return columns;
}

/** Applies a status-change answer to the cached active list without waiting for the next poll. */
export function applyOrderUpdate(orders: readonly BaristaOrder[], updated: BaristaOrder): BaristaOrder[] {
  const rest = orders.filter((o) => o.id !== updated.id);
  const stillActive = (QUEUE_COLUMNS as readonly string[]).includes(updated.status);
  return stillActive ? [...rest, updated] : rest;
}
