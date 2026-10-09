import { useQuery } from '@tanstack/react-query';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { baristaApi } from '../api/index.ts';
import { queryKeys } from '../api/queryKeys.ts';
import { categoryKey } from '../i18n/keys.ts';
import { ConnectionBanner } from '../ui/ConnectionBanner.tsx';
import { LoadError } from '../ui/LoadError.tsx';
import { countUnavailable, groupMenu } from './groups.ts';
import { MenuRow } from './MenuRow.tsx';
import styles from './StopListPage.module.css';

const REFRESH_MS = 15_000;

/**
 * Stop list: the whole menu by category with an in-stock switch per item.
 * Refreshed every 15 s so a change made on another tablet shows up.
 */
export function StopListPage() {
  const { t } = useTranslation();
  const titleId = useId();
  const query = useQuery({
    queryKey: queryKeys.menu(),
    queryFn: ({ signal }) => baristaApi.listMenu(signal),
    refetchInterval: REFRESH_MS,
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

  const groups = groupMenu(query.data);
  const out = countUnavailable(query.data);

  return (
    <section aria-labelledby={titleId} className={styles.page}>
      <header className={styles.header}>
        <h1 id={titleId} className={styles.title}>
          {t('menu.title')}
        </h1>
        <p className={styles.hint}>{t('menu.hint')}</p>
        <p className={`${styles.out} ${out > 0 ? styles.outActive : ''}`}>{t('menu.outCount', { n: out })}</p>
      </header>

      {query.isRefetchError && <ConnectionBanner error={query.error} />}

      {groups.length === 0 && <p className={styles.muted}>{t('menu.empty')}</p>}

      {groups.map((group) => (
        <section key={group.category} className={styles.group} aria-labelledby={`${titleId}-${group.category}`}>
          <h2 id={`${titleId}-${group.category}`} className={styles.groupTitle}>
            {t(categoryKey(group.category))}
          </h2>
          <ul className={styles.list}>
            {group.items.map((item) => (
              <MenuRow key={item.id} item={item} />
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}
