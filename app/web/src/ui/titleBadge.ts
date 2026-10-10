import { useSyncExternalStore } from 'react';

/**
 * How many new orders the barista has not looked at yet. The order watcher
 * (signed-in area) writes it; the document title (every screen, including the
 * ones outside the layout) reads it.
 */
let unseen = 0;
const listeners = new Set<() => void>();

export function setUnseenOrders(count: number): void {
  if (count === unseen) return;
  unseen = count;
  listeners.forEach((listener) => {
    listener();
  });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useUnseenOrders(): number {
  return useSyncExternalStore(
    subscribe,
    () => unseen,
    () => 0,
  );
}
