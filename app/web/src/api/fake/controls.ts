import type { BaristaOrder } from '../types.ts';

/**
 * Dev-only levers for the fake backend: they let a developer (or a browser
 * test) provoke the situations the panel must survive without a real server.
 * Exposed as `window.brewqFake` in `npm run dev` with the fake layer.
 */
export interface FakeControls {
  /** A customer checks out: a new NEW order appears for the next poll. */
  addOrder(): BaristaOrder;
  /**
   * Another device moves the order one step forward behind the panel's back
   * (default: the oldest active one). The panel's next click on it must get
   * 409 INVALID_STATUS_TRANSITION. Returns the order after the move, or null.
   */
  advanceBehindUi(orderId?: number): BaristaOrder | null;
  /** Every call fails with NETWORK until set back to false. */
  setOffline(offline: boolean): void;
  /** The next call fails with this HTTP error (e.g. 429 RATE_LIMITED, 500 INTERNAL_ERROR). */
  failNext(code: string, status: number): void;
  /** The server forgets the session: the next call gets 401 BARISTA_UNAUTHORIZED. */
  expireSession(): void;
}
