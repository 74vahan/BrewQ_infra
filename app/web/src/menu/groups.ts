import { CATEGORIES } from '../api/types.ts';
import type { MenuItem } from '../api/types.ts';

export interface MenuGroup {
  /** Category value as the server sent it (may be one this build does not know). */
  category: string;
  items: MenuItem[];
}

/**
 * Menu items grouped by category: coffee, tea, cake first (the contract's
 * order), then any category from the future in order of appearance. Item order
 * inside a group is kept as the server sent it (by name).
 */
export function groupMenu(items: readonly MenuItem[]): MenuGroup[] {
  const groups = new Map<string, MenuItem[]>();
  for (const category of CATEGORIES) groups.set(category, []);
  for (const item of items) {
    const list = groups.get(item.category);
    if (list) list.push(item);
    else groups.set(item.category, [item]);
  }
  return [...groups]
    .filter(([, list]) => list.length > 0)
    .map(([category, list]) => ({ category, items: list }));
}

/** Copy of the list with one item's availability replaced (optimistic update / rollback). */
export function withAvailability(items: readonly MenuItem[], id: number, isAvailable: boolean): MenuItem[] {
  return items.map((item) => (item.id === id ? { ...item, is_available: isAvailable } : item));
}

export function countUnavailable(items: readonly MenuItem[]): number {
  return items.filter((item) => !item.is_available).length;
}
