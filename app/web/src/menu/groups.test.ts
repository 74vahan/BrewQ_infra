import { describe, expect, it } from 'vitest';
import type { MenuItem } from '../api/types.ts';
import { countUnavailable, groupMenu, withAvailability } from './groups.ts';

function item(id: number, category: string, available = true): MenuItem {
  return {
    id,
    name: `Item ${String(id)}`,
    category: category as MenuItem['category'],
    sizes: [{ size: 'M', price_amd: 1000 }],
    is_available: available,
    image_url: null,
  };
}

describe('groupMenu', () => {
  it('orders groups coffee, tea, cake and keeps the server order inside', () => {
    const groups = groupMenu([item(1, 'cake'), item(2, 'coffee'), item(3, 'tea'), item(4, 'coffee')]);
    expect(groups.map((g) => g.category)).toEqual(['coffee', 'tea', 'cake']);
    expect(groups[0]?.items.map((i) => i.id)).toEqual([2, 4]);
  });

  it('omits empty categories and appends unknown ones at the end', () => {
    const groups = groupMenu([item(1, 'soup'), item(2, 'tea')]);
    expect(groups.map((g) => g.category)).toEqual(['tea', 'soup']);
  });
});

describe('withAvailability / countUnavailable', () => {
  it('changes one item without touching the input', () => {
    const items = [item(1, 'tea'), item(2, 'tea')];
    const next = withAvailability(items, 2, false);
    expect(next[1]?.is_available).toBe(false);
    expect(items[1]?.is_available).toBe(true);
    expect(countUnavailable(next)).toBe(1);
  });
});
