import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { playChime } from '../sound/chime.ts';
import { setUnseenOrders } from '../ui/titleBadge.ts';
import { useSoundEnabled } from '../ui/useSoundEnabled.ts';
import { acknowledgeFresh, markFresh, resetFresh, useFreshState } from './freshOrders.ts';
import { createNewOrderTracker } from './newOrderTracker.ts';
import type { NewOrderTracker } from './newOrderTracker.ts';
import { useActiveOrders } from './useActiveOrders.ts';

const ACKNOWLEDGE_EVENTS = ['pointerdown', 'keydown'] as const;

/**
 * Mounted once in the layout, so a new order is noticed on every screen (the
 * barista may be on the stop list or "Today" when it arrives).
 *
 * On each new order: the chime (if the barista has sound on and the browser
 * allows it), the highlight on the card, a "(2) Queue · BrewQ" counter in the
 * tab title, and a polite announcement for screen readers. Any touch or key press
 * counts as "seen" and clears the highlight and the counter.
 */
export function NewOrderWatcher() {
  const { t } = useTranslation();
  const { data } = useActiveOrders();
  const [soundOn] = useSoundEnabled();
  const fresh = useFreshState();
  const trackerRef = useRef<NewOrderTracker | null>(null);

  useEffect(() => {
    if (!data) return;
    trackerRef.current ??= createNewOrderTracker();
    const arrived = trackerRef.current.observe(data);
    if (arrived.length === 0) return;
    markFresh(arrived);
    if (soundOn) void playChime();
  }, [data, soundOn]);

  useEffect(() => {
    ACKNOWLEDGE_EVENTS.forEach((type) => {
      window.addEventListener(type, acknowledgeFresh, { passive: true });
    });
    return () => {
      ACKNOWLEDGE_EVENTS.forEach((type) => {
        window.removeEventListener(type, acknowledgeFresh);
      });
      resetFresh();
    };
  }, []);

  // Only orders that are still waiting count: one already taken is no longer "new".
  const waiting = data?.filter((order) => order.status === 'NEW' && fresh.ids.has(order.id)).length ?? 0;

  // The counter itself is drawn into the tab title by <DocumentTitle>.
  useEffect(() => {
    setUnseenOrders(waiting);
    return () => {
      setUnseenOrders(0);
    };
  }, [waiting]);

  return (
    <p className="visually-hidden" role="status">
      {fresh.latestCodes.length > 0 ? t('queue.newOrder', { code: fresh.latestCodes.join(', ') }) : ''}
    </p>
  );
}
