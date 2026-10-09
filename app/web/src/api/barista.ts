import { clearSession, getToken } from '../auth/tokenStore.ts';
import { request } from './client.ts';
import { ApiError } from './errors.ts';
import type {
  BaristaOrder,
  LoginResponse,
  MenuItem,
  OrderScope,
  TargetStatus,
} from './types.ts';

/**
 * The barista API as the UI sees it. `httpBaristaApi` talks to the backend;
 * `fake/fakeBarista.ts` implements the same interface in memory so the panel
 * can be built before the backend exists. The choice is made in `index.ts`.
 */
export interface BaristaApi {
  login(password: string): Promise<LoginResponse>;
  listOrders(scope: OrderScope, signal?: AbortSignal): Promise<BaristaOrder[]>;
  changeStatus(orderId: number, to: TargetStatus): Promise<BaristaOrder>;
  listMenu(signal?: AbortSignal): Promise<MenuItem[]>;
  setAvailability(menuItemId: number, isAvailable: boolean): Promise<MenuItem>;
}

interface ItemsResponse<T> {
  items: T[];
}

interface AuthedOptions {
  method?: 'GET' | 'POST' | 'PATCH';
  body?: unknown;
  signal?: AbortSignal | undefined;
}

/** Adds the Bearer token; any 401 BARISTA_UNAUTHORIZED drops the session. */
async function authed<T>(path: string, options: AuthedOptions = {}): Promise<T> {
  const token = getToken();
  if (!token) {
    clearSession();
    throw new ApiError('BARISTA_UNAUTHORIZED', 401);
  }
  try {
    return await request<T>(path, { ...options, token });
  } catch (error) {
    if (error instanceof ApiError && error.code === 'BARISTA_UNAUTHORIZED') clearSession();
    throw error;
  }
}

export const httpBaristaApi: BaristaApi = {
  login: (password) =>
    request<LoginResponse>('/barista/login', { method: 'POST', body: { password } }),

  listOrders: async (scope, signal) => {
    const data = await authed<ItemsResponse<BaristaOrder>>(`/barista/orders?scope=${scope}`, {
      signal,
    });
    return data.items;
  },

  changeStatus: (orderId, to) =>
    authed<BaristaOrder>(`/barista/orders/${String(orderId)}/status`, {
      method: 'POST',
      body: { to },
    }),

  listMenu: async (signal) => {
    const data = await authed<ItemsResponse<MenuItem>>('/barista/menu', { signal });
    return data.items;
  },

  setAvailability: (menuItemId, isAvailable) =>
    authed<MenuItem>(`/barista/menu/${String(menuItemId)}`, {
      method: 'PATCH',
      body: { is_available: isAvailable },
    }),
};
