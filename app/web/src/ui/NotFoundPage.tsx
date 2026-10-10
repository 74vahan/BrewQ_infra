import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { LanguageSwitch } from './LanguageSwitch.tsx';
import styles from './NotFoundPage.module.css';
import { Wordmark } from './Wordmark.tsx';

/**
 * "Page not found" in the panel's style. Standalone (no header, no sign-in
 * needed to see it); the link goes to the queue, and anyone who is signed out
 * is sent on to the sign-in screen from there.
 */
export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <main className={styles.page} id="main">
      <div className={styles.language}>
        <LanguageSwitch />
      </div>

      <section className={styles.card} aria-labelledby="not-found-title">
        <Wordmark />
        <p className={styles.code} aria-hidden="true">
          404
        </p>
        <h1 id="not-found-title" className={styles.title}>
          {t('notFound.title')}
        </h1>
        <p className={styles.body}>{t('notFound.body')}</p>
        <Link className={styles.back} to="/">
          {t('notFound.back')}
        </Link>
      </section>
    </main>
  );
}
