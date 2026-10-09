import type { OrderScope } from './types.ts';

/** TanStack Query keys, in one place so mutations can invalidate precisely. */
export const queryKeys = {
  /** Prefix of every orders query (active and today): invalidate with it. */
  ordersAll: () => ['barista', 'orders'] as const,
  orders: (scope: OrderScope) => ['barista', 'orders', scope] as const,
  menu: () => ['barista', 'menu'] as const,
};

/** Panel polling cadence (memory/03-api.md, "Polling"). */
export const POLL_INTERVAL_MS = 5000;
