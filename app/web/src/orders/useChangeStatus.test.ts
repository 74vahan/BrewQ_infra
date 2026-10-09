import { MutationObserver, QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it } from 'vitest';
import { queryKeys } from '../api/queryKeys.ts';
import type { BaristaOrder } from '../api/types.ts';
import { createFakeBackend } from '../api/fake/fakeBarista.ts';
import { clearSession, saveSession } from '../auth/tokenStore.ts';
import { clearNotices, getNotices } from '../notices/noticeStore.ts';
import { changeStatusOptions } from './useChangeStatus.ts';

function setup() {
  const backend = createFakeBackend('', { latencyMs: 0 });
  saveSession({ token: 'test-token', expiresAt: new Date(Date.now() + 3_600_000).toISOString() });
  const queryClient = new QueryClient();
  const run = (orderId: number, to: Parameters<typeof backend.api.changeStatus>[1]) =>
    new MutationObserver(queryClient, changeStatusOptions(queryClient, backend.api)).mutate({ orderId, to });
  const isInvalidated = (): boolean =>
    queryClient.getQueryState(queryKeys.orders('active'))?.isInvalidated === true;
  return { backend, queryClient, run, isInvalidated };
}

async function seedCache(backend: ReturnType<typeof setup>['backend'], queryClient: QueryClient) {
  const orders = await backend.api.listOrders('active');
  queryClient.setQueryData(queryKeys.orders('active'), orders);
  return orders;
}

beforeEach(() => {
  clearSession();
  clearNotices();
});

describe('changing the status from the panel', () => {
  it('success: the cache shows the new status at once and is marked for refetch', async () => {
    const { backend, queryClient, run, isInvalidated } = setup();
    const { id } = backend.controls.addOrder();
    await seedCache(backend, queryClient);

    await run(id, 'IN_PROGRESS');

    const cached = queryClient.getQueryData<BaristaOrder[]>(queryKeys.orders('active'));
    expect(cached?.find((o) => o.id === id)?.status).toBe('IN_PROGRESS');
    expect(isInvalidated()).toBe(true);
    expect(getNotices()).toHaveLength(0);
  });

  it('picked up: the order disappears from the cached queue', async () => {
    const { backend, queryClient, run } = setup();
    const ready = (await seedCache(backend, queryClient)).find((o) => o.status === 'READY');
    await run(ready?.id ?? 0, 'PICKED_UP');
    const cached = queryClient.getQueryData<BaristaOrder[]>(queryKeys.orders('active'));
    expect(cached?.some((o) => o.id === ready?.id)).toBe(false);
  });

  it('409: refetches and shows "already changed" as a warning', async () => {
    const { backend, queryClient, run, isInvalidated } = setup();
    const { id } = backend.controls.addOrder();
    await seedCache(backend, queryClient);
    backend.controls.advanceBehindUi(id); // someone else started it first

    await expect(run(id, 'IN_PROGRESS')).rejects.toMatchObject({ code: 'INVALID_STATUS_TRANSITION', status: 409 });

    expect(isInvalidated()).toBe(true);
    expect(getNotices()).toMatchObject([{ messageKey: 'errors.INVALID_STATUS_TRANSITION', tone: 'warning' }]);
  });

  it('429: shows the rate-limit message, no refetch', async () => {
    const { backend, queryClient, run, isInvalidated } = setup();
    const { id } = backend.controls.addOrder();
    await seedCache(backend, queryClient);
    backend.controls.failNext('RATE_LIMITED', 429);

    await expect(run(id, 'IN_PROGRESS')).rejects.toMatchObject({ status: 429 });

    expect(isInvalidated()).toBe(false);
    expect(getNotices()).toMatchObject([{ messageKey: 'errors.RATE_LIMITED', tone: 'error' }]);
  });

  it('network failure: shows the offline message and leaves the cache alone', async () => {
    const { backend, queryClient, run } = setup();
    const { id } = backend.controls.addOrder();
    const before = await seedCache(backend, queryClient);
    backend.controls.setOffline(true);

    await expect(run(id, 'IN_PROGRESS')).rejects.toMatchObject({ code: 'NETWORK' });

    expect(getNotices()).toMatchObject([{ messageKey: 'errors.NETWORK' }]);
    expect(queryClient.getQueryData(queryKeys.orders('active'))).toEqual(before);
  });

  it('401: no notice (the router sends the barista to sign in)', async () => {
    const { backend, queryClient, run } = setup();
    const { id } = backend.controls.addOrder();
    await seedCache(backend, queryClient);
    backend.controls.expireSession();

    await expect(run(id, 'IN_PROGRESS')).rejects.toMatchObject({ status: 401 });

    expect(getNotices()).toHaveLength(0);
  });
});
