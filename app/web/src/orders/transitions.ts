import { actionKey } from '../i18n/keys.ts';
import { ORDER_STATUSES } from '../api/types.ts';
import type { BaristaOrder, OrderStatus, TargetStatus } from '../api/types.ts';

/**
 * Which buttons an order card shows. The ONLY input is the server's
 * `allowed_transitions`; the panel never decides on its own which step is legal.
 * Two defensive filters on top of it:
 *  - a target this build has no label for is dropped (a status from the future);
 *  - a target that would go backwards is dropped: the panel never draws a
 *    "back" button, even if a server bug offered one (memory/02-database.md).
 */
export interface OrderActions {
  /** Forward moves (start, ready, picked up), in the server's order. */
  forward: TargetStatus[];
  /** Cancellation is offered separately (secondary button, with confirmation). */
  canCancel: boolean;
}

const RANK: Record<OrderStatus, number> = Object.fromEntries(
  ORDER_STATUSES.map((status, index) => [status, index]),
) as Record<OrderStatus, number>;

function rankOf(status: string): number {
  return RANK[status as OrderStatus] ?? Number.POSITIVE_INFINITY;
}

export function actionsFor(order: Pick<BaristaOrder, 'status' | 'allowed_transitions'>): OrderActions {
  const known = order.allowed_transitions.filter((to) => actionKey(to) !== null);
  const forward = known.filter((to) => to !== 'CANCELLED' && rankOf(to) > rankOf(order.status));
  return { forward, canCancel: known.includes('CANCELLED') };
}
