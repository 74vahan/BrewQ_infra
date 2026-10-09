import { useQuery } from '@tanstack/react-query';
import { baristaApi } from '../api/index.ts';
import { POLL_INTERVAL_MS, queryKeys } from '../api/queryKeys.ts';

/**
 * The live queue: GET /api/barista/orders?scope=active every 5 s, also while
 * the tab is in the background (a tablet by the espresso machine is rarely the
 * focused window). The queue screen and the new-order watcher share this query.
 */
export function useActiveOrders() {
  return useQuery({
    queryKey: queryKeys.orders('active'),
    queryFn: ({ signal }) => baristaApi.listOrders('active', signal),
    refetchInterval: POLL_INTERVAL_MS,
    refetchIntervalInBackground: true,
  });
}
