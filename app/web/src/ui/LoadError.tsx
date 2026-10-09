import { useTranslation } from 'react-i18next';
import { ErrorMessage } from './ErrorMessage.tsx';
import styles from './LoadError.module.css';

/** A screen that has no data at all and could not load it: the reason plus a retry button. */
export function LoadError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className={styles.box}>
      <ErrorMessage error={error} />
      <button type="button" className={styles.retry} onClick={onRetry}>
        {t('common.retry')}
      </button>
    </div>
  );
}
