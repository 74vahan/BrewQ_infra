import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { BaristaOrder } from '../api/types.ts';
import { OrderCard } from './OrderCard.tsx';
import styles from './QueueColumn.module.css';
import { StatusChip } from './StatusChip.tsx';

interface QueueColumnProps {
  status: string;
  orders: readonly BaristaOrder[];
  now: number;
  freshIds: ReadonlySet<number>;
}

/** One status column of the queue: heading with the count, then the tickets, oldest first. */
export function QueueColumn({ status, orders, now, freshIds }: QueueColumnProps) {
  const { t } = useTranslation();
  const headingId = useId();

  return (
    <section className={styles.column} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        <StatusChip status={status} size="large" />
        <span className={styles.count}>{orders.length}</span>
      </h2>

      {orders.length === 0 ? (
        <p className={styles.empty}>{t('queue.empty')}</p>
      ) : (
        <ul className={styles.list}>
          {orders.map((order) => (
            <li key={order.id} className={styles.entry}>
              <OrderCard order={order} now={now} mode="queue" fresh={freshIds.has(order.id)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
