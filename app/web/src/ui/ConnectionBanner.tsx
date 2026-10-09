import { useTranslation } from 'react-i18next';
import { toApiError } from '../api/errors.ts';
import { errorKey } from '../i18n/keys.ts';
import styles from './ConnectionBanner.module.css';

/**
 * A refresh failed but the screen still has older data: keep the data, say
 * what is wrong above it. Polling continues by itself and clears the banner
 * as soon as one request succeeds.
 */
export function ConnectionBanner({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const { code } = toApiError(error);

  return (
    <p className={styles.banner} role="status">
      {code === 'NETWORK' ? t('common.offline') : `${t(errorKey(code))} ${t('common.showingLatest')}`}
    </p>
  );
}
