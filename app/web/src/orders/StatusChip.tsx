import { useTranslation } from 'react-i18next';
import { statusKey } from '../i18n/keys.ts';
import styles from './StatusChip.module.css';

const TONE: Record<string, string | undefined> = {
  NEW: styles['new'],
  IN_PROGRESS: styles['progress'],
  READY: styles['ready'],
  PICKED_UP: styles['done'],
  CANCELLED: styles['cancelled'],
};

/** Status as a dot plus its translated name; colour is never the only carrier. */
export function StatusChip({ status, size = 'normal' }: { status: string; size?: 'normal' | 'large' }) {
  const { t } = useTranslation();
  return (
    <span className={`${styles['chip'] ?? ''} ${size === 'large' ? (styles['large'] ?? '') : ''} ${TONE[status] ?? styles['done'] ?? ''}`}>
      <span className={styles['dot']} aria-hidden="true" />
      {t(statusKey(status))}
    </span>
  );
}
