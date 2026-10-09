import { isKnownErrorCode } from '../api/errorCodes.ts';
import { CATEGORIES, ORDER_STATUSES, SIZES } from '../api/types.ts';

/**
 * Translation keys for values that come from the server. The server may send
 * a value this build has never heard of; each helper then returns the
 * neutral "unknown" key instead of a missing string (memory/03-api.md).
 */

const STATUSES = new Set<string>(ORDER_STATUSES);
const SIZE_SET = new Set<string>(SIZES);
const CATEGORY_SET = new Set<string>(CATEGORIES);

export function statusKey(status: string): string {
  return STATUSES.has(status) ? `status.${status}` : 'status.unknown';
}

/** Label of the button that moves an order to `status` (only non-NEW targets). */
export function actionKey(status: string): string | null {
  return STATUSES.has(status) && status !== 'NEW' ? `action.${status}` : null;
}

export function sizeKey(size: string): string {
  return SIZE_SET.has(size) ? `size.${size}` : 'size.unknown';
}

export function categoryKey(category: string): string {
  return CATEGORY_SET.has(category) ? `category.${category}` : 'category.unknown';
}

export function errorKey(code: string): string {
  return isKnownErrorCode(code) ? `errors.${code}` : 'errors.UNKNOWN';
}
