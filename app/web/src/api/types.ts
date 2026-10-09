/**
 * Response shapes of the barista part of the API.
 * Source of truth: memory/03-api.md (hand-written, keep in sync).
 *
 * The unions list the values the contract knows today. The server may add
 * more later, so UI code must never assume a value is one of these: use the
 * helpers in `i18n/keys.ts`, which fall back to a neutral label.
 */

export const SIZES = ['S', 'M', 'L'] as const;
export type Size = (typeof SIZES)[number];

export const CATEGORIES = ['coffee', 'tea', 'cake'] as const;
export type Category = (typeof CATEGORIES)[number];

export const ORDER_STATUSES = ['NEW', 'IN_PROGRESS', 'READY', 'PICKED_UP', 'CANCELLED'] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

/** Statuses a barista can request via POST /api/barista/orders/{id}/status. */
export type TargetStatus = Exclude<OrderStatus, 'NEW'>;

/** ISO 8601 UTC with a trailing Z, e.g. "2026-10-09T08:15:30.123456Z". */
export type IsoDateTime = string;

export interface MenuItemSize {
  size: Size;
  price_amd: number;
}

export interface MenuItem {
  id: number;
  name: string;
  category: Category;
  /** Only the offered sizes, in S, M, L order. */
  sizes: MenuItemSize[];
  is_available: boolean;
  /** Relative path ("/media/menu/latte.webp") or null (use a category placeholder). */
  image_url: string | null;
}

export interface OrderItem {
  menu_item_id: number;
  name: string;
  size: Size;
  qty: number;
  unit_price_amd: number;
  line_total_amd: number;
}

export interface BaristaOrder {
  id: number;
  /** Pickup code, "A-007". */
  code: string;
  status: OrderStatus;
  total_amd: number;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  items: OrderItem[];
  customer_name: string | null;
  /** The only source for which action buttons to draw. */
  allowed_transitions: TargetStatus[];
}

export interface LoginResponse {
  token: string;
  expires_at: IsoDateTime;
}

export type OrderScope = 'active' | 'today';

/** Server-provided `details` of an error envelope; always an object. */
export type ErrorDetails = Record<string, unknown>;
