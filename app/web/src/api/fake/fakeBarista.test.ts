import { beforeEach, describe, expect, it } from 'vitest';
import { clearSession, getToken, saveSession } from '../../auth/tokenStore.ts';
import { ApiError } from '../errors.ts';
import { createFakeBackend } from './fakeBarista.ts';

function signedIn() {
  const backend = createFakeBackend('', { latencyMs: 0 });
  saveSession({ token: 'test-token', expiresAt: new Date(Date.now() + 3_600_000).toISOString() });
  return backend;
}

async function failureOf(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error('expected the call to fail');
}

beforeEach(() => {
  clearSession();
});

describe('fake backend follows the contract', () => {
  it('lists active orders oldest first and today newest first', async () => {
    const { api } = signedIn();
    const active = await api.listOrders('active');
    expect(active.every((o) => ['NEW', 'IN_PROGRESS', 'READY'].includes(o.status))).toBe(true);
    expect(active.map((o) => o.created_at)).toEqual([...active.map((o) => o.created_at)].sort());

    const today = await api.listOrders('today');
    expect(today.length).toBeGreaterThan(active.length);
    expect(today.map((o) => o.created_at)).toEqual([...today.map((o) => o.created_at)].sort().reverse());
  });

  it('walks NEW -> IN_PROGRESS -> READY -> PICKED_UP, then leaves the queue but stays in today', async () => {
    const { api, controls } = signedIn();
    const { id } = controls.addOrder();
    expect((await api.changeStatus(id, 'IN_PROGRESS')).allowed_transitions).toEqual(['READY', 'CANCELLED']);
    expect((await api.changeStatus(id, 'READY')).allowed_transitions).toEqual(['PICKED_UP']);
    const done = await api.changeStatus(id, 'PICKED_UP');
    expect(done.allowed_transitions).toEqual([]);

    expect((await api.listOrders('active')).some((o) => o.id === id)).toBe(false);
    expect((await api.listOrders('today')).find((o) => o.id === id)?.status).toBe('PICKED_UP');
  });

  it('cancels from NEW but not from READY', async () => {
    const { api, controls } = signedIn();
    const fresh = controls.addOrder();
    expect((await api.changeStatus(fresh.id, 'CANCELLED')).status).toBe('CANCELLED');

    const ready = (await api.listOrders('active')).find((o) => o.status === 'READY');
    expect(ready).toBeDefined();
    const error = await failureOf(api.changeStatus(ready?.id ?? 0, 'CANCELLED'));
    expect(error.code).toBe('INVALID_STATUS_TRANSITION');
    expect(error.status).toBe(409);
  });

  it('never moves backwards or repeats a step (second tap gets 409, not a further step)', async () => {
    const { api, controls } = signedIn();
    const { id } = controls.addOrder();
    await api.changeStatus(id, 'IN_PROGRESS');
    const repeat = await failureOf(api.changeStatus(id, 'IN_PROGRESS'));
    expect(repeat.code).toBe('INVALID_STATUS_TRANSITION');
    expect(repeat.details).toMatchObject({ from: 'IN_PROGRESS', to: 'IN_PROGRESS', allowed: ['READY', 'CANCELLED'] });
    const back = await failureOf(api.changeStatus(id, 'IN_PROGRESS'));
    expect(back.status).toBe(409);
  });

  it('a race: another device moved the order, so the panel click gets 409 with the actual state', async () => {
    const { api, controls } = signedIn();
    const { id } = controls.addOrder();
    controls.advanceBehindUi(id);
    const error = await failureOf(api.changeStatus(id, 'IN_PROGRESS'));
    expect(error.code).toBe('INVALID_STATUS_TRANSITION');
    expect(error.details).toMatchObject({ from: 'IN_PROGRESS' });
  });

  it('404 for an unknown order', async () => {
    const { api } = signedIn();
    expect((await failureOf(api.changeStatus(999, 'READY'))).code).toBe('ORDER_NOT_FOUND');
  });

  it('a new customer order shows up as NEW with the next code', async () => {
    const { api, controls } = signedIn();
    const before = (await api.listOrders('active')).length;
    const added = controls.addOrder();
    expect(added.status).toBe('NEW');
    expect(added.code).toMatch(/^A-\d{3}$/);
    expect((await api.listOrders('active')).length).toBe(before + 1);
  });

  it('menu: coffee, tea, cake order; availability toggles; 404 for unknown id', async () => {
    const { api } = signedIn();
    const menu = await api.listMenu();
    const categories = menu.map((m) => m.category);
    expect(categories.indexOf('tea')).toBeGreaterThan(categories.lastIndexOf('coffee'));
    expect(categories.indexOf('cake')).toBeGreaterThan(categories.lastIndexOf('tea'));
    expect(menu.some((m) => m.image_url === null)).toBe(true);

    const latte = menu.find((m) => m.name === 'Latte');
    expect((await api.setAvailability(latte?.id ?? 0, false)).is_available).toBe(false);
    expect((await api.listMenu()).find((m) => m.name === 'Latte')?.is_available).toBe(false);
    expect((await failureOf(api.setAvailability(999, true))).code).toBe('MENU_ITEM_NOT_FOUND');
  });
});

describe('fake backend failures the panel must survive', () => {
  it('no token: 401 BARISTA_UNAUTHORIZED', async () => {
    const backend = createFakeBackend('', { latencyMs: 0 });
    expect((await failureOf(backend.api.listOrders('active'))).code).toBe('BARISTA_UNAUTHORIZED');
  });

  it('expired session drops the token and answers 401 once', async () => {
    const { api, controls } = signedIn();
    controls.expireSession();
    expect((await failureOf(api.listOrders('active'))).status).toBe(401);
    expect(getToken()).toBeNull();
  });

  it('wrong password on login: 401 BARISTA_INVALID_PASSWORD', async () => {
    const backend = createFakeBackend('right', { latencyMs: 0 });
    expect((await failureOf(backend.api.login('wrong'))).code).toBe('BARISTA_INVALID_PASSWORD');
    expect((await backend.api.login('right')).token).not.toBe('');
  });

  it('failNext injects exactly one failure (429), then recovers', async () => {
    const { api, controls } = signedIn();
    controls.failNext('RATE_LIMITED', 429);
    expect((await failureOf(api.listOrders('active'))).status).toBe(429);
    await expect(api.listOrders('active')).resolves.toBeDefined();
  });

  it('offline: every call fails with NETWORK until it is back', async () => {
    const { api, controls } = signedIn();
    controls.setOffline(true);
    expect((await failureOf(api.listMenu())).code).toBe('NETWORK');
    controls.setOffline(false);
    await expect(api.listMenu()).resolves.toBeDefined();
  });
});
