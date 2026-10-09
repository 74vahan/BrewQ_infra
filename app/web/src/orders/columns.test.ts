import { describe, expect, it } from 'vitest';
import type { BaristaOrder, OrderStatus } from '../api/types.ts';
import { applyOrderUpdate, groupByStatus } from './columns.ts';
import { countByStatus } from './summary.ts';

function order(id: number, status: string, minute: number): BaristaOrder {
  return {
    id,
    code: `A-${String(id).padStart(3, '0')}`,
    status: status as OrderStatus,
    total_amd: 0,
    created_at: `2026-10-09T08:${String(minute).padStart(2, '0')}:00Z`,
    updated_at: '2026-10-09T08:00:00Z',
    items: [],
    customer_name: null,
    allowed_transitions: [],
  };
}

describe('groupByStatus', () => {
  it('splits into the three columns, oldest first, and skips unknown statuses', () => {
    const columns = groupByStatus([
      order(3, 'NEW', 30),
      order(1, 'NEW', 10),
      order(2, 'READY', 20),
      order(4, 'IN_PROGRESS', 5),
      order(5, 'ARCHIVED', 1),
    ]);
    expect(columns.NEW.map((o) => o.id)).toEqual([1, 3]);
    expect(columns.IN_PROGRESS.map((o) => o.id)).toEqual([4]);
    expect(columns.READY.map((o) => o.id)).toEqual([2]);
  });
});

describe('applyOrderUpdate', () => {
  it('replaces an order that stays active', () => {
    const next = applyOrderUpdate([order(1, 'NEW', 1), order(2, 'NEW', 2)], order(1, 'IN_PROGRESS', 1));
    expect(next.find((o) => o.id === 1)?.status).toBe('IN_PROGRESS');
    expect(next).toHaveLength(2);
  });

  it('removes an order that left the queue (picked up / cancelled)', () => {
    expect(applyOrderUpdate([order(1, 'READY', 1)], order(1, 'PICKED_UP', 1))).toEqual([]);
    expect(applyOrderUpdate([order(1, 'NEW', 1)], order(1, 'CANCELLED', 1))).toEqual([]);
  });
});

describe('countByStatus', () => {
  it('counts in workflow order and omits empty statuses', () => {
    const counts = countByStatus([order(1, 'PICKED_UP', 1), order(2, 'NEW', 2), order(3, 'PICKED_UP', 3)]);
    expect(counts).toEqual([
      { status: 'NEW', count: 1 },
      { status: 'PICKED_UP', count: 2 },
    ]);
  });
});
