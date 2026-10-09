import type { Category, MenuItem, OrderStatus, TargetStatus } from '../types.ts';

/**
 * Demo data for the fake data layer (dev only; never part of a production
 * build). The menu mirrors backend/seed/menu.json: English names, SVG images
 * under /media/menu/. One item has no image to exercise the category placeholder.
 */

type PriceRow = readonly [s: number | null, m: number | null, l: number | null];

const ROWS: readonly (readonly [string, Category, PriceRow, string | null])[] = [
  ['Espresso', 'coffee', [700, 900, 1100], 'espresso'],
  ['Americano', 'coffee', [800, 1000, 1200], 'americano'],
  ['Cappuccino', 'coffee', [1000, 1200, 1400], 'cappuccino'],
  ['Latte', 'coffee', [1100, 1300, 1500], 'latte'],
  ['Flat White', 'coffee', [1100, 1300, 1500], 'flat-white'],
  ['Mocha', 'coffee', [1200, 1400, 1600], null],
  ['Black Tea', 'tea', [700, 900, 1100], 'black-tea'],
  ['Green Tea', 'tea', [700, 900, 1100], 'green-tea'],
  ['Masala Chai', 'tea', [null, 1200, 1500], 'masala-chai'],
  ['Cheesecake', 'cake', [null, 1500, null], 'cheesecake'],
  ['Napoleon', 'cake', [null, 1400, null], 'napoleon'],
  ['Brownie', 'cake', [null, 1200, null], 'brownie'],
];

export function seedMenu(): MenuItem[] {
  return ROWS.map(([name, category, [s, m, l], image], index) => {
    const sizes: MenuItem['sizes'] = [];
    if (s !== null) sizes.push({ size: 'S', price_amd: s });
    if (m !== null) sizes.push({ size: 'M', price_amd: m });
    if (l !== null) sizes.push({ size: 'L', price_amd: l });
    return {
      id: index + 1,
      name,
      category,
      sizes,
      // Flat White starts on the stop list, as the real menu may have it.
      is_available: name !== 'Flat White',
      image_url: image === null ? null : `/media/menu/${image}.svg`,
    };
  });
}

/** Which statuses may follow which (mirrors memory/02-database.md). */
export const NEXT_STATUSES: Record<OrderStatus, TargetStatus[]> = {
  NEW: ['IN_PROGRESS', 'CANCELLED'],
  IN_PROGRESS: ['READY', 'CANCELLED'],
  READY: ['PICKED_UP'],
  PICKED_UP: [],
  CANCELLED: [],
};
