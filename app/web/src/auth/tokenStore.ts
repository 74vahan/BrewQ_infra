import type { IsoDateTime } from '../api/types.ts';

/**
 * Barista session in localStorage (why not sessionStorage: memory/06-decisions.md, B9).
 * Stores the token with its `expires_at`; an expired or malformed record is
 * treated as "no session". Falls back to memory when storage is unavailable
 * (private mode), so the panel still works until the tab is closed.
 */

const KEY = 'brewq.barista.session';

export interface Session {
  token: string;
  expiresAt: IsoDateTime;
}

type Listener = () => void;
const listeners = new Set<Listener>();
let memorySession: Session | null = null;

function parseSession(raw: string | null): Session | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== 'object' || value === null) return null;
    const { token, expiresAt } = value as Record<string, unknown>;
    if (typeof token !== 'string' || token === '' || typeof expiresAt !== 'string') return null;
    return { token, expiresAt };
  } catch {
    return null;
  }
}

export function isExpired(session: Session, now: number = Date.now()): boolean {
  const expires = Date.parse(session.expiresAt);
  return Number.isNaN(expires) || expires <= now;
}

function readStored(): Session | null {
  try {
    return parseSession(localStorage.getItem(KEY));
  } catch {
    return memorySession;
  }
}

function notify(): void {
  listeners.forEach((listener) => {
    listener();
  });
}

export function getSession(): Session | null {
  const session = readStored();
  return session && !isExpired(session) ? session : null;
}

/** Stable primitive snapshot for useSyncExternalStore. */
export function getToken(): string | null {
  return getSession()?.token ?? null;
}

export function saveSession(session: Session): void {
  memorySession = session;
  try {
    localStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // Storage blocked: the in-memory copy keeps the session for this tab.
  }
  notify();
}

export function clearSession(): void {
  memorySession = null;
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to remove if storage is blocked.
  }
  notify();
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent): void => {
    if (event.key === KEY || event.key === null) listener();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', onStorage);
  };
}
