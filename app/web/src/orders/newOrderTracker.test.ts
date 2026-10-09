import { describe, expect, it } from 'vitest';
import type { BaristaOrder, OrderStatus } from '../api/types.ts';
import { createNewOrderTracker } from './newOrderTracker.ts';

function order(id: number, status: OrderStatus = 'NEW'): BaristaOrder {
  return {
    id,
    code: `A-${String(id).padStart(3, '0')}`,
    status,
    total_amd: 1000,
    created_at: `2026-10-09T08:${String(id).padStart(2, '0')}:00Z`,
    updated_at: '2026-10-09T08:00:00Z',
    items: [],
    customer_name: null,
    allowed_transitions: [],
  };
}

const ids = (orders: BaristaOrder[]): number[] => orders.map((o) => o.id);

describe('createNewOrderTracker', () => {
  it('the first poll is the baseline: waiting orders do not signal', () => {
    const tracker = createNewOrderTracker();
    expect(tracker.observe([order(1), order(2)])).toEqual([]);
  });

  it('an id that appears in a later poll signals once', () => {
    const tracker = createNewOrderTracker();
    tracker.observe([order(1)]);
    expect(ids(tracker.observe([order(1), order(2)]))).toEqual([2]);
    expect(tracker.observe([order(1), order(2)])).toEqual([]);
  });

  it('several new orders come back oldest first', () => {
    const tracker = createNewOrderTracker();
    tracker.observe([]);
    expect(ids(tracker.observe([order(5), order(3), order(4)]))).toEqual([3, 4, 5]);
  });

  it('an empty first poll still counts as the baseline', () => {
    const tracker = createNewOrderTracker();
    tracker.observe([]);
    expect(ids(tracker.observe([order(1)]))).toEqual([1]);
  });

  it('an order that drops out of one poll and comes back does not signal twice', () => {
    const tracker = createNewOrderTracker();
    tracker.observe([order(1)]);
    tracker.observe([order(1), order(2)]);
    tracker.observe([order(1)]);
    expect(tracker.observe([order(1), order(2)])).toEqual([]);
  });

  it('a status change of a known order is not a new order', () => {
    const tracker = createNewOrderTracker();
    tracker.observe([order(1, 'NEW')]);
    expect(tracker.observe([order(1, 'IN_PROGRESS')])).toEqual([]);
  });

  it('an order that first shows up already taken by someone else does not signal', () => {
    const tracker = createNewOrderTracker();
    tracker.observe([order(1)]);
    expect(tracker.observe([order(1), order(2, 'IN_PROGRESS')])).toEqual([]);
  });
});
