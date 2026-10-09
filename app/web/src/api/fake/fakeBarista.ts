import { clearSession, getToken } from '../../auth/tokenStore.ts';
import type { BaristaApi } from '../barista.ts';
import { ApiError } from '../errors.ts';
import type { BaristaOrder, MenuItem, OrderStatus } from '../types.ts';
import type { FakeControls } from './controls.ts';
import { randomNewOrder, seedOrders } from './orderFactory.ts';
import { NEXT_STATUSES, seedMenu } from './seed.ts';

/**
 * In-memory implementation of BaristaApi for development before the backend
 * exists. It follows the same contract (shapes, error codes, ordering, the
 * status machine), so swapping it for the real client changes nothing in the UI.
 *
 * Login: when `acceptedPassword` is empty any non-empty password works,
 * otherwise it must match. The value comes from a dev-only env variable, so no
 * password is ever written in code.
 */

const TOKEN_TTL_MS = 12 * 60 * 60 * 1000;
const ACTIVE: readonly OrderStatus[] = ['NEW', 'IN_PROGRESS', 'READY'];
const CATEGORY_ORDER = ['coffee', 'tea', 'cake'];

export interface FakeBackend {
  api: BaristaApi;
  controls: FakeControls;
}

export interface FakeOptions {
  /** Simulated network latency; tests pass 0. */
  latencyMs?: number;
}

const byCreatedAsc = (a: BaristaOrder, b: BaristaOrder): number =>
  a.created_at.localeCompare(b.created_at) || a.id - b.id;

/** Menu order of the contract: coffee, tea, cake, then by name. */
const byMenuOrder = (a: MenuItem, b: MenuItem): number =>
  CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category) || a.name.localeCompare(b.name);

export function createFakeBackend(acceptedPassword = '', { latencyMs = 120 }: FakeOptions = {}): FakeBackend {
  const menu: MenuItem[] = seedMenu();
  const orders: BaristaOrder[] = seedOrders(menu);
  let nextOrderId = orders.length + 1;
  let offline = false;
  let sessionExpired = false;
  let pendingFailure: { code: string; status: number } | null = null;

  /** Every call goes through here: latency, then the injected failures. */
  async function gate(authenticated: boolean): Promise<void> {
    if (latencyMs > 0) await new Promise((resolve) => setTimeout(resolve, latencyMs));
    if (offline) throw new ApiError('NETWORK', 0);
    if (pendingFailure) {
      const { code, status } = pendingFailure;
      pendingFailure = null;
      throw new ApiError(code, status);
    }
    if (authenticated && (sessionExpired || !getToken())) {
      sessionExpired = false;
      clearSession();
      throw new ApiError('BARISTA_UNAUTHORIZED', 401);
    }
  }

  function move(order: BaristaOrder, to: OrderStatus): void {
    order.status = to;
    order.updated_at = new Date().toISOString();
    order.allowed_transitions = NEXT_STATUSES[to];
  }

  const api: BaristaApi = {
    async login(password) {
      await gate(false);
      const valid = acceptedPassword === '' ? password !== '' : password === acceptedPassword;
      if (!valid) throw new ApiError('BARISTA_INVALID_PASSWORD', 401);
      sessionExpired = false;
      return {
        token: `fake.${Math.random().toString(36).slice(2)}`,
        expires_at: new Date(Date.now() + TOKEN_TTL_MS).toISOString(),
      };
    },

    async listOrders(scope) {
      await gate(true);
      if (scope === 'active') {
        return orders
          .filter((o) => ACTIVE.includes(o.status))
          .sort(byCreatedAsc)
          .map((o) => structuredClone(o));
      }
      return [...orders].sort((a, b) => byCreatedAsc(b, a)).map((o) => structuredClone(o));
    },

    async changeStatus(orderId, to) {
      await gate(true);
      const order = orders.find((o) => o.id === orderId);
      if (!order) throw new ApiError('ORDER_NOT_FOUND', 404, { order_id: orderId });
      const allowed = NEXT_STATUSES[order.status];
      if (!allowed.includes(to)) {
        throw new ApiError('INVALID_STATUS_TRANSITION', 409, { from: order.status, to, allowed });
      }
      move(order, to);
      return structuredClone(order);
    },

    async listMenu() {
      await gate(true);
      return [...menu].sort(byMenuOrder).map((m) => structuredClone(m));
    },

    async setAvailability(menuItemId, isAvailable) {
      await gate(true);
      const item = menu.find((m) => m.id === menuItemId);
      if (!item) throw new ApiError('MENU_ITEM_NOT_FOUND', 404, { menu_item_id: menuItemId });
      item.is_available = isAvailable;
      return structuredClone(item);
    },
  };

  const controls: FakeControls = {
    addOrder() {
      const order = randomNewOrder(menu, nextOrderId);
      nextOrderId += 1;
      orders.push(order);
      return structuredClone(order);
    },
    advanceBehindUi(orderId) {
      const order =
        orderId === undefined
          ? orders.filter((o) => ACTIVE.includes(o.status)).sort(byCreatedAsc)[0]
          : orders.find((o) => o.id === orderId);
      const next = order ? NEXT_STATUSES[order.status].find((s) => s !== 'CANCELLED') : undefined;
      if (!order || !next) return null;
      move(order, next);
      return structuredClone(order);
    },
    setOffline(value) {
      offline = value;
    },
    failNext(code, status) {
      pendingFailure = { code, status };
    },
    expireSession() {
      sessionExpired = true;
    },
  };

  return { api, controls };
}
