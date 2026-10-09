import { useSyncExternalStore } from 'react';

/**
 * Short messages above the content ("The order was already changed"). They
 * outlive the card or row that caused them, which is why they are not local
 * component state. Each one disappears by itself or when dismissed.
 */

export interface Notice {
  id: number;
  messageKey: string;
  tone: 'warning' | 'error';
}

const AUTO_DISMISS_MS = 7000;
const MAX_VISIBLE = 3;

let notices: readonly Notice[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(next: readonly Notice[]): void {
  notices = next;
  listeners.forEach((listener) => {
    listener();
  });
}

export function dismissNotice(id: number): void {
  emit(notices.filter((notice) => notice.id !== id));
}

export function pushNotice(messageKey: string, tone: Notice['tone']): void {
  // The same message twice in a row (two failed taps) is shown once.
  if (notices.some((notice) => notice.messageKey === messageKey)) return;
  const notice: Notice = { id: nextId, messageKey, tone };
  nextId += 1;
  emit([...notices, notice].slice(-MAX_VISIBLE));
  setTimeout(() => {
    dismissNotice(notice.id);
  }, AUTO_DISMISS_MS);
}

/** Current notices (the hook below is for components; this is for plain code and tests). */
export function getNotices(): readonly Notice[] {
  return notices;
}

export function clearNotices(): void {
  emit([]);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useNotices(): readonly Notice[] {
  return useSyncExternalStore(
    subscribe,
    () => notices,
    () => [],
  );
}
