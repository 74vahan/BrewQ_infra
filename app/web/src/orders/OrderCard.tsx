import { useTranslation } from 'react-i18next';
import type { BaristaOrder } from '../api/types.ts';
import { formatAmd } from '../format/money.ts';
import { formatClock, minutesSince } from '../format/time.ts';
import { sizeKey } from '../i18n/keys.ts';
import { useLanguage } from '../i18n/useLanguage.ts';
import styles from './OrderCard.module.css';
import { StatusActions } from './StatusActions.tsx';
import { StatusChip } from './StatusChip.tsx';

interface OrderCardProps {
  order: BaristaOrder;
  /** Current time, for "4 min ago"; shared by all cards so one timer serves the screen. */
  now: number;
  /** 'queue': action buttons and relative time; 'today': read-only with the status shown. */
  mode: 'queue' | 'today';
  /** Arrived since the barista last looked at the screen. */
  fresh?: boolean;
}

/**
 * An order as a ticket: the pickup code (the same number the customer sees)
 * on the stub, a perforation, the items, then the total and the actions.
 */
export function OrderCard({ order, now, mode, fresh = false }: OrderCardProps) {
  const { t } = useTranslation();
  const language = useLanguage();
  const codeId = `order-${String(order.id)}-code`;
  const clock = formatClock(order.created_at, language);
  const minutes = minutesSince(order.created_at, now);
  const age = minutes === 0 ? t('queue.justNow') : t('queue.minutesAgo', { minutes });

  return (
    <article className={`${styles.card} ${fresh ? styles.fresh : ''}`} aria-labelledby={codeId}>
      {fresh && <span className={styles.badge}>{t('queue.newBadge')}</span>}

      <header className={styles.stub}>
        <h3 id={codeId} className={styles.code} translate="no">
          {order.code}
        </h3>
        <div className={styles.meta}>
          {order.customer_name && <p className={styles.customer}>{order.customer_name}</p>}
          <p className={styles.time}>
            <time dateTime={order.created_at}>{mode === 'queue' ? age : clock}</time>
            {mode === 'queue' && clock !== '' && <span className={styles.clock}> · {clock}</span>}
          </p>
        </div>
      </header>

      <div className={styles.perforation} aria-hidden="true" />

      <ul className={styles.items} aria-label={t('order.items')}>
        {order.items.map((item, index) => (
          <li key={`${String(item.menu_item_id)}-${item.size}-${String(index)}`} className={styles.item}>
            <span className={styles.itemName}>{item.name}</span>
            <span className={styles.size}>{t(sizeKey(item.size))}</span>
            <span className={styles.qty}>× {item.qty}</span>
          </li>
        ))}
      </ul>

      <footer className={styles.foot}>
        <p className={styles.total}>
          <span className={styles.totalLabel}>{t('order.total')}</span>
          <span className={styles.amount}>{formatAmd(order.total_amd, language)}</span>
        </p>
        {mode === 'queue' ? <StatusActions order={order} /> : <StatusChip status={order.status} />}
      </footer>
    </article>
  );
}
