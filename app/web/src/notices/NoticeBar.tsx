import { useTranslation } from 'react-i18next';
import styles from './NoticeBar.module.css';
import { dismissNotice, useNotices } from './noticeStore.ts';

/** Region for the messages of noticeStore; polite live region so screen readers announce them. */
export function NoticeBar() {
  const { t } = useTranslation();
  const notices = useNotices();

  return (
    <div className={styles.region} role="status" aria-live="polite">
      {notices.map((notice) => (
        <div key={notice.id} className={`${styles.notice} ${notice.tone === 'error' ? styles.error : styles.warning}`}>
          <p className={styles.text}>{t(notice.messageKey)}</p>
          <button
            type="button"
            className={styles.close}
            aria-label={t('common.dismiss')}
            onClick={() => {
              dismissNotice(notice.id);
            }}
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>
      ))}
    </div>
  );
}
