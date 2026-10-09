import { useCallback, useSyncExternalStore } from 'react';

/**
 * "Play a sound on a new order" preference (header toggle). Defaults to on.
 * The new-order alert of the queue screen reads it; here it is only stored.
 */

const KEY = 'brewq.sound';
const listeners = new Set<() => void>();
let memoryValue = true;

function read(): boolean {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === null) return memoryValue;
    return raw !== 'off';
  } catch {
    return memoryValue;
  }
}

function write(enabled: boolean): void {
  memoryValue = enabled;
  try {
    localStorage.setItem(KEY, enabled ? 'on' : 'off');
  } catch {
    // Blocked storage: the in-memory value lasts until the tab closes.
  }
  listeners.forEach((listener) => {
    listener();
  });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener('storage', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', listener);
  };
}

export function useSoundEnabled(): [boolean, (enabled: boolean) => void] {
  const enabled = useSyncExternalStore(subscribe, read, () => true);
  const setEnabled = useCallback((value: boolean) => {
    write(value);
  }, []);
  return [enabled, setEnabled];
}
