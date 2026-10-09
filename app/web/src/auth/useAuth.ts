import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { baristaApi } from '../api/index.ts';
import { clearSession, getSession, getToken, saveSession, subscribe } from './tokenStore.ts';

/** setTimeout cannot take more than a signed 32-bit number of milliseconds. */
const MAX_TIMEOUT_MS = 2 ** 31 - 1;

export interface Auth {
  isAuthenticated: boolean;
  /** Rejects with an ApiError (BARISTA_INVALID_PASSWORD, RATE_LIMITED, ...). */
  login: (password: string) => Promise<void>;
  logout: () => void;
}

export function useAuth(): Auth {
  const token = useSyncExternalStore(subscribe, getToken, () => null);
  const queryClient = useQueryClient();

  const login = useCallback(async (password: string) => {
    const { token: newToken, expires_at: expiresAt } = await baristaApi.login(password);
    saveSession({ token: newToken, expiresAt });
  }, []);

  const logout = useCallback(() => {
    clearSession();
    queryClient.clear();
  }, [queryClient]);

  return { isAuthenticated: token !== null, login, logout };
}

/**
 * Mounted once, inside the signed-in area: signs the barista out when the
 * token expires, and drops cached data whenever the session disappears
 * (expiry, 401 from the API, sign-out in another tab).
 */
export function useSessionLifecycle(): void {
  const token = useSyncExternalStore(subscribe, getToken, () => null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (token === null) {
      queryClient.clear();
      return;
    }
    const session = getSession();
    if (!session) return;
    const remaining = Date.parse(session.expiresAt) - Date.now();
    const timer = setTimeout(clearSession, Math.min(Math.max(remaining, 0), MAX_TIMEOUT_MS));
    return () => {
      clearTimeout(timer);
    };
  }, [token, queryClient]);
}
