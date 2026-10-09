import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { baristaApi } from '../api/index.ts';
import { POLL_INTERVAL_MS, queryKeys } from '../api/queryKeys.ts';
import { ConnectionBanner } from '../ui/ConnectionBanner.tsx';
import { LoadError } from '../ui/LoadError.tsx';
import { useNow } from '../ui/useNow.ts';
import { OrderCard } from './OrderCard.tsx';
import { StatusChip } from './StatusChip.tsx';
import { countByStatus } from './summary.ts';
import styles from './TodayPage.module.css';

/** Read-only list of the whole Yerevan day, newest first, including picked up and cancelled. */
export function TodayPage() {
  const { t } = useTranslation();
  const now = useNow(60_000);
  const query = useQuery({
    queryKey: queryKeys.orders('today'),
    queryFn: ({ signal }) => baristaApi.listOrders('today', signal),
    refetchInterval: POLL_INTERVAL_MS,
  });

  if (query.isPending) {
    return <p className={styles.muted}>{t('common.loading')}</p>;
  }
  if (!query.data) {
    return (
      <LoadError
        error={query.error}
        onRetry={() => {
          void query.refetch();
        }}
      />
    );
  }

  const orders = query.data;

  return (
    <section aria-labelledby="today-title">
      <header className={styles.header}>
        <h1 id="today-title" className={styles.title}>
          {t('today.title')}
        </h1>
        <ul className={styles.counts}>
          {countByStatus(orders).map(({ status, count }) => (
            <li key={status} className={styles.count}>
              <StatusChip status={status} />
              <span className={styles.number}>{count}</span>
            </li>
          ))}
        </ul>
      </header>

      {query.isRefetchError && <ConnectionBanner error={query.error} />}

      {orders.length === 0 ? (
        <p className={styles.empty}>{t('today.empty')}</p>
      ) : (
        <ul className={styles.grid}>
          {orders.map((order) => (
            <li key={order.id} className={styles.entry}>
              <OrderCard order={order} now={now} mode="today" />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
