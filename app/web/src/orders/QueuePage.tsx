import { useTranslation } from 'react-i18next';
import { ConnectionBanner } from '../ui/ConnectionBanner.tsx';
import { LoadError } from '../ui/LoadError.tsx';
import { LoadingState } from '../ui/LoadingState.tsx';
import { useNow } from '../ui/useNow.ts';
import { QUEUE_COLUMNS, groupByStatus } from './columns.ts';
import { useFreshState } from './freshOrders.ts';
import { QueueColumn } from './QueueColumn.tsx';
import styles from './QueuePage.module.css';
import { useActiveOrders } from './useActiveOrders.ts';

/** Main screen: the live queue in three columns (new, in progress, ready). */
export function QueuePage() {
  const { t } = useTranslation();
  const query = useActiveOrders();
  const now = useNow(30_000);
  const { ids: freshIds } = useFreshState();

  if (query.isPending) {
    return <LoadingState shape="board" />;
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

  const columns = groupByStatus(query.data);
  const isEmpty = QUEUE_COLUMNS.every((status) => columns[status].length === 0);

  return (
    <div>
      <h1 className="visually-hidden">{t('queue.title')}</h1>
      {query.isRefetchError && <ConnectionBanner error={query.error} />}

      {isEmpty ? (
        <p className={styles.allClear}>{t('queue.allClear')}</p>
      ) : (
        <div className={styles.board}>
          {QUEUE_COLUMNS.map((status) => (
            <QueueColumn key={status} status={status} orders={columns[status]} now={now} freshIds={freshIds} />
          ))}
        </div>
      )}
    </div>
  );
}
