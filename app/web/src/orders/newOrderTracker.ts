import type { BaristaOrder } from '../api/types.ts';

/**
 * Decides which orders of a poll deserve the "new order" signal.
 *
 *  - The first poll after the panel opens is the baseline: orders that were
 *    already waiting do not beep.
 *  - Afterwards an order signals once, the first time its id appears (the set
 *    of seen ids only grows, so a flaky poll that drops and restores an order
 *    does not beep twice).
 *  - Only orders that are NEW signal: one that shows up already in progress was
 *    taken by someone else, there is nothing to alert about.
 */
export interface NewOrderTracker {
  /** Feed every poll result; returns the orders to signal (oldest first). */
  observe(orders: readonly BaristaOrder[]): BaristaOrder[];
}

export function createNewOrderTracker(): NewOrderTracker {
  const seen = new Set<number>();
  let baselined = false;

  return {
    observe(orders) {
      const fresh = baselined
        ? orders
            .filter((order) => !seen.has(order.id) && order.status === 'NEW')
            .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id)
        : [];
      for (const order of orders) seen.add(order.id);
      baselined = true;
      return fresh;
    },
  };
}
