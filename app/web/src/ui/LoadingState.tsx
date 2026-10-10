import { useTranslation } from 'react-i18next';
import styles from './LoadingState.module.css';

type Shape = 'board' | 'grid' | 'list';

function Blocks({ count, className }: { count: number; className: string | undefined }) {
  return Array.from({ length: count }, (_, index) => <div key={index} className={`${styles.block} ${className}`} />);
}

/**
 * Skeleton for a screen whose first load is running. The shapes are
 * decorative; screen readers get the "Loading…" text through the status role.
 *   board - three queue columns (the queue), grid - ticket grid (today), list - menu rows (stop list)
 */
export function LoadingState({ shape }: { shape: Shape }) {
  const { t } = useTranslation();

  return (
    <div role="status" aria-busy="true">
      <span className="visually-hidden">{t('common.loading')}</span>
      <div aria-hidden="true">
        {shape === 'board' && (
          <div className={styles.board}>
            {[0, 1, 2].map((column) => (
              <div key={column} className={styles.column}>
                <div className={`${styles.block} ${styles.heading}`} />
                <Blocks count={2} className={styles.card} />
              </div>
            ))}
          </div>
        )}
        {shape === 'grid' && (
          <div className={styles.grid}>
            <Blocks count={6} className={styles.card} />
          </div>
        )}
        {shape === 'list' && (
          <div className={styles.list}>
            <Blocks count={8} className={styles.row} />
          </div>
        )}
      </div>
    </div>
  );
}
