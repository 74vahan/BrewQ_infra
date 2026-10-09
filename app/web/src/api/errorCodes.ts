/**
 * Every `error.code` the panel knows how to translate (memory/03-api.md),
 * plus two codes the client invents itself:
 *  - NETWORK: the request never got an HTTP answer (offline, timeout, DNS);
 *  - UNKNOWN: an answer that is not an error envelope (nginx 502/504 pages).
 *
 * The list is the contract between the API client and the locale files:
 * i18n tests and ci/check-i18n.mjs require an `errors.<CODE>` string for
 * each entry.
 */
export const API_ERROR_CODES = [
  'VALIDATION_ERROR',
  'DEVICE_ID_MISSING',
  'DEVICE_ID_INVALID',
  'SIZE_NOT_OFFERED',
  'BARISTA_INVALID_PASSWORD',
  'BARISTA_UNAUTHORIZED',
  'NOT_FOUND',
  'MENU_ITEM_NOT_FOUND',
  'CART_ITEM_NOT_FOUND',
  'ORDER_NOT_FOUND',
  'METHOD_NOT_ALLOWED',
  'MENU_ITEM_UNAVAILABLE',
  'CART_QTY_LIMIT_EXCEEDED',
  'CART_EMPTY',
  'CART_HAS_UNAVAILABLE_ITEMS',
  'ACTIVE_ORDER_EXISTS',
  'DAILY_ORDER_LIMIT_REACHED',
  'ORDER_NOT_CANCELLABLE',
  'INVALID_STATUS_TRANSITION',
  'RATE_LIMITED',
  'INTERNAL_ERROR',
  'SERVICE_UNAVAILABLE',
  'NETWORK',
  'UNKNOWN',
] as const;

export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

const KNOWN = new Set<string>(API_ERROR_CODES);

export function isKnownErrorCode(code: string): code is ApiErrorCode {
  return KNOWN.has(code);
}
