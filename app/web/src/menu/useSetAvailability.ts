import { useMutation, useQueryClient } from '@tanstack/react-query';
import { baristaApi } from '../api/index.ts';
import { queryKeys } from '../api/queryKeys.ts';
import type { MenuItem } from '../api/types.ts';
import { reactToFailure } from '../notices/noticeErrors.ts';
import { pushNotice } from '../notices/noticeStore.ts';
import { withAvailability } from './groups.ts';

interface AvailabilityVariables {
  menuItemId: number;
  isAvailable: boolean;
}

const MUTATION_KEY = ['barista', 'menu', 'availability'] as const;

/**
 * PATCH /api/barista/menu/{id} with an optimistic update: the switch flips at
 * once, and if the request fails only THAT item goes back (another row's switch
 * that is still in flight is left alone) and the error is shown.
 */
export function useSetAvailability() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: MUTATION_KEY,
    mutationFn: ({ menuItemId, isAvailable }: AvailabilityVariables) =>
      baristaApi.setAvailability(menuItemId, isAvailable),

    onMutate: async ({ menuItemId, isAvailable }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.menu() });
      const previous = queryClient
        .getQueryData<MenuItem[]>(queryKeys.menu())
        ?.find((item) => item.id === menuItemId)?.is_available;
      queryClient.setQueryData<MenuItem[]>(queryKeys.menu(), (old) =>
        old ? withAvailability(old, menuItemId, isAvailable) : old,
      );
      return { previous };
    },

    onError: (error, { menuItemId }, context) => {
      const { previous } = context ?? {};
      if (previous !== undefined) {
        queryClient.setQueryData<MenuItem[]>(queryKeys.menu(), (old) =>
          old ? withAvailability(old, menuItemId, previous) : old,
        );
      }
      const reaction = reactToFailure(error);
      if (!reaction.silent) pushNotice(reaction.messageKey, reaction.tone);
    },

    // Re-read the truth once the last switch in flight has settled.
    onSettled: () => {
      if (queryClient.isMutating({ mutationKey: MUTATION_KEY }) <= 1) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.menu() });
      }
    },
  });
}
