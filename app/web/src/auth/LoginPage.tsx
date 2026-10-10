import { useId, useRef, useState } from 'react';
import type { SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router';
import { isFakeApi } from '../api/index.ts';
import { unlockAudio } from '../sound/chime.ts';
import { ErrorMessage } from '../ui/ErrorMessage.tsx';
import { LanguageSwitch } from '../ui/LanguageSwitch.tsx';
import { Wordmark } from '../ui/Wordmark.tsx';
import styles from './LoginPage.module.css';
import { useAuth } from './useAuth.ts';

/** Only same-app absolute paths are honoured as a post-login destination. */
function safeDestination(from: unknown): string {
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && from !== '/login'
    ? from
    : '/';
}

export function LoginPage() {
  const { t } = useTranslation();
  const { isAuthenticated, login } = useAuth();
  const location = useLocation();
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [emptyPassword, setEmptyPassword] = useState(false);
  const hasError = error !== null || emptyPassword;
  const passwordId = useId();
  const errorId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  if (isAuthenticated) {
    const from = (location.state as { from?: unknown } | null)?.from;
    return <Navigate to={safeDestination(from)} replace />;
  }

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    if (password === '') {
      setEmptyPassword(true);
      inputRef.current?.focus();
      return;
    }
    setEmptyPassword(false);
    // The sign-in click is the user gesture that lets the browser play the new-order sound later.
    unlockAudio();
    setPending(true);
    setError(null);
    try {
      await login(password);
    } catch (caught) {
      setError(caught);
      setPassword('');
      inputRef.current?.focus();
    } finally {
      setPending(false);
    }
  };

  return (
    <main className={styles.page} id="main">
      <div className={styles.language}>
        <LanguageSwitch />
      </div>

      <div className={styles.ticket}>
        <header className={styles.stub}>
          <p className={styles.eyebrow}>{t('app.subtitle')}</p>
          <Wordmark size="xl" />
        </header>

        <div className={styles.perforation} aria-hidden="true" />

        <form className={styles.form} onSubmit={(event) => void onSubmit(event)} noValidate>
          <h1 className={styles.title}>{t('auth.title')}</h1>

          <label className={styles.label} htmlFor={passwordId}>
            {t('auth.password')}
          </label>
          <input
            id={passwordId}
            ref={inputRef}
            className={styles.input}
            spellCheck={false}
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              setEmptyPassword(false);
            }}
            aria-invalid={hasError}
            aria-describedby={hasError ? errorId : undefined}
          />
          <p className={styles.hint}>{t('auth.hint')}</p>

          {emptyPassword && <ErrorMessage id={errorId} message={t('auth.passwordRequired')} />}
          {error !== null && !emptyPassword && <ErrorMessage id={errorId} error={error} />}

          <button className={styles.submit} type="submit" disabled={pending}>
            {pending && <span className={styles.spinner} aria-hidden="true" />}
            {pending ? t('auth.submitting') : t('auth.submit')}
          </button>
        </form>

        {isFakeApi && <p className={styles.fake}>{t('dev.fakeApi')}</p>}
      </div>
    </main>
  );
}
