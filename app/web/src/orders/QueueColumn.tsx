import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { BaristaOrder } from '../api/types.ts';
import { ColumnProgress } from './ColumnProgress.tsx';
import { QUEUE_COLUMNS } from './columns.ts';
import { OrderCard } from './OrderCard.tsx';
import styles from './QueueColumn.module.css';
import { StatusChip } from './StatusChip.tsx';

interface QueueColumnProps {
  status: string;
  orders: readonly BaristaOrder[];
  now: number;
  freshIds: ReadonlySet<number>;
}

/** One status column of the queue: heading with the count and progress, then the tickets, oldest first. */
export function QueueColumn({ status, orders, now, freshIds }: QueueColumnProps) {
  const { t } = useTranslation();
  const headingId = useId();
  const position = Math.max(0, (QUEUE_COLUMNS as readonly string[]).indexOf(status));

  return (
    <section className={styles.column} aria-labelledby={headingId}>
      <div className={styles.head}>
        <h2 id={headingId} className={styles.heading}>
          <StatusChip status={status} size="large" />
          <span className={styles.count}>{orders.length}</span>
        </h2>
        <ColumnProgress position={position} total={QUEUE_COLUMNS.length} />
      </div>

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
