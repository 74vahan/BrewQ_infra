import { useSyncExternalStore } from 'react';

/**
 * Orders that arrived since the barista last touched the screen: they get the
 * highlight and count in the tab title. Kept in a small store (not component
 * state) because the watcher in the layout writes it while the queue screen,
 * the title and the screen-reader announcement read it.
 */
export interface FreshState {
  ids: ReadonlySet<number>;
  /** Codes of the latest batch, announced to screen readers. */
  latestCodes: readonly string[];
}

const EMPTY: FreshState = { ids: new Set(), latestCodes: [] };

let state: FreshState = EMPTY;
const listeners = new Set<() => void>();

function emit(next: FreshState): void {
  state = next;
  listeners.forEach((listener) => {
    listener();
  });
}

export function markFresh(orders: readonly { id: number; code: string }[]): void {
  emit({
    ids: new Set([...state.ids, ...orders.map((order) => order.id)]),
    latestCodes: orders.map((order) => order.code),
  });
}

/** The barista is looking at the screen: nothing is "unseen" any more. */
export function acknowledgeFresh(): void {
  if (state.ids.size > 0) emit({ ids: new Set(), latestCodes: state.latestCodes });
}

export function resetFresh(): void {
  emit(EMPTY);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useFreshState(): FreshState {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => EMPTY,
  );
}
