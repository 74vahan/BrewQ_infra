import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { BaristaApi } from '../api/barista.ts';
import { baristaApi } from '../api/index.ts';
import { queryKeys } from '../api/queryKeys.ts';
import type { BaristaOrder, TargetStatus } from '../api/types.ts';
import { pushNotice } from '../notices/noticeStore.ts';
import { reactToFailure } from '../notices/noticeErrors.ts';
import { applyOrderUpdate } from './columns.ts';

export interface ChangeStatusVariables {
  orderId: number;
  to: TargetStatus;
}

/**
 * POST /api/barista/orders/{id}/status.
 *
 * On success the queue is patched from the answer at once (the card hops to
 * its new column without waiting for the next poll) and then refetched to
 * confirm. A poll that was already in flight is cancelled first, otherwise its
 * older answer could put the card back for a moment.
 *
 * On 409 / 404 the order was changed elsewhere: the lists are refetched and a
 * "The order was already changed" notice is shown (see reactToFailure).
 *
 * Plain options (no React) so the behaviour can be tested with a bare QueryClient.
 */
export function changeStatusOptions(queryClient: QueryClient, api: Pick<BaristaApi, 'changeStatus'> = baristaApi) {
  return {
    mutationFn: ({ orderId, to }: ChangeStatusVariables) => api.changeStatus(orderId, to),

    onSuccess: async (updated: BaristaOrder) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.orders('active') });
      queryClient.setQueryData<BaristaOrder[]>(queryKeys.orders('active'), (old) =>
        old ? applyOrderUpdate(old, updated) : old,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.ordersAll() });
    },

    onError: (error: unknown) => {
      const reaction = reactToFailure(error);
      if (!reaction.silent) pushNotice(reaction.messageKey, reaction.tone);
      if (reaction.refetch) void queryClient.invalidateQueries({ queryKey: queryKeys.ordersAll() });
    },
  };
}

export function useChangeStatus() {
  const queryClient = useQueryClient();
  return useMutation(changeStatusOptions(queryClient));
}
