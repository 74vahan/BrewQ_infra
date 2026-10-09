import type { BaristaOrder, MenuItem, OrderItem, OrderStatus, Size } from '../types.ts';
import { NEXT_STATUSES } from './seed.ts';

/** Builds demo orders for the fake data layer. */

export function orderCode(number: number): string {
  return `A-${String(number).padStart(3, '0')}`;
}

function line(menu: readonly MenuItem[], menuId: number, size: Size, qty: number): OrderItem {
  const item = menu.find((m) => m.id === menuId);
  const price = item?.sizes.find((s) => s.size === size)?.price_amd ?? 0;
  return {
    menu_item_id: menuId,
    name: item?.name ?? '',
    size,
    qty,
    unit_price_amd: price,
    line_total_amd: price * qty,
  };
}

export type LineSpec = readonly [menuId: number, size: Size, qty: number];

export function buildOrder(
  menu: readonly MenuItem[],
  id: number,
  status: OrderStatus,
  createdAt: Date,
  customer: string | null,
  specs: readonly LineSpec[],
): BaristaOrder {
  const items = specs.map(([menuId, size, qty]) => line(menu, menuId, size, qty));
  const iso = createdAt.toISOString();
  return {
    id,
    code: orderCode(id),
    status,
    total_amd: items.reduce((sum, i) => sum + i.line_total_amd, 0),
    created_at: iso,
    updated_at: iso,
    items,
    customer_name: customer,
    allowed_transitions: NEXT_STATUSES[status],
  };
}

const NAMES: readonly (string | null)[] = ['Ani', null, 'Armen', 'Mariam', null, 'Tigran', 'Lilit'];

/** A random NEW order from items that are on sale, like a customer checking out. */
export function randomNewOrder(menu: readonly MenuItem[], id: number, random: () => number = Math.random): BaristaOrder {
  const available = menu.filter((m) => m.is_available && m.sizes.length > 0);
  const pick = <T>(list: readonly T[]): T => list[Math.floor(random() * list.length)] as T;
  const lineCount = 1 + Math.floor(random() * 2);
  const specs: LineSpec[] = [];
  for (let i = 0; i < lineCount; i += 1) {
    const item = pick(available);
    specs.push([item.id, pick(item.sizes).size, 1 + Math.floor(random() * 2)]);
  }
  return buildOrder(menu, id, 'NEW', new Date(), pick(NAMES), specs);
}

/** Starting queue: one order in each active status plus a finished and a cancelled one. */
export function seedOrders(menu: readonly MenuItem[]): BaristaOrder[] {
  const ago = (minutes: number): Date => new Date(Date.now() - minutes * 60_000);
  return [
    buildOrder(menu, 1, 'READY', ago(14), 'Ani', [[4, 'M', 2]]),
    buildOrder(menu, 2, 'IN_PROGRESS', ago(9), null, [
      [3, 'L', 1],
      [10, 'M', 1],
    ]),
    buildOrder(menu, 3, 'NEW', ago(4), 'Armen', [[2, 'S', 1]]),
    buildOrder(menu, 4, 'NEW', ago(1), null, [
      [8, 'M', 2],
      [11, 'M', 1],
    ]),
    buildOrder(menu, 5, 'PICKED_UP', ago(40), 'Mariam', [[4, 'S', 1]]),
    buildOrder(menu, 6, 'CANCELLED', ago(55), null, [[7, 'L', 1]]),
  ];
}
