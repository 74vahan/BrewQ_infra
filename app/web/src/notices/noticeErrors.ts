import { toApiError } from '../api/errors.ts';
import { errorKey } from '../i18n/keys.ts';

/** How the panel reacts to a failed action (status change, availability switch). */
export interface FailureReaction {
  /** Translation key of the message for the barista. */
  messageKey: string;
  /** 'warning' = the world moved on (not the barista's fault), 'error' = something broke. */
  tone: 'warning' | 'error';
  /** The cached lists are stale: fetch them again right now. */
  refetch: boolean;
  /** The session is gone: no message, the router already sends the barista to /login. */
  silent: boolean;
}

/**
 * - 409 INVALID_STATUS_TRANSITION / 404 ORDER_NOT_FOUND: somebody else (another
 *   tablet, the customer cancelling) changed the order first. Refetch quietly
 *   and say so: "The order was already changed".
 * - 401 BARISTA_UNAUTHORIZED: the API client already dropped the token and
 *   RequireAuth redirects to the sign-in page; a toast would be noise.
 * - everything else (429, network, 5xx, unknown): show the translated message.
 */
export function reactToFailure(error: unknown): FailureReaction {
  const { code } = toApiError(error);
  const messageKey = errorKey(code);
  if (code === 'INVALID_STATUS_TRANSITION' || code === 'ORDER_NOT_FOUND') {
    return { messageKey, tone: 'warning', refetch: true, silent: false };
  }
  if (code === 'BARISTA_UNAUTHORIZED') {
    return { messageKey, tone: 'error', refetch: false, silent: true };
  }
  return { messageKey, tone: 'error', refetch: false, silent: false };
}
