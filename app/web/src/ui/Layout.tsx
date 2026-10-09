import { useTranslation } from 'react-i18next';
import { NavLink, Outlet } from 'react-router';
import { useAuth } from '../auth/useAuth.ts';
import { NoticeBar } from '../notices/NoticeBar.tsx';
import { NewOrderWatcher } from '../orders/NewOrderWatcher.tsx';
import { SoundHint } from '../sound/SoundHint.tsx';
import { DemoBar } from './DemoBar.tsx';
import { LogoutIcon } from './icons.tsx';
import styles from './Layout.module.css';
import { LanguageSwitch } from './LanguageSwitch.tsx';
import { SoundToggle } from './SoundToggle.tsx';
import { Wordmark } from './Wordmark.tsx';

const NAV_ITEMS = [
  { to: '/', titleKey: 'queue.title', end: true },
  { to: '/today', titleKey: 'today.title', end: false },
  { to: '/menu', titleKey: 'menu.title', end: false },
] as const;

/** Frame of the signed-in area: header with navigation and controls, content below. */
export function Layout() {
  const { t } = useTranslation();
  const { logout } = useAuth();

  return (
    <div className={styles.shell}>
      <a className={styles.skip} href="#main">
        {t('a11y.skipToContent')}
      </a>

      <header className={styles.header}>
        <div className={styles.brand}>
          <Wordmark />
        </div>

        <nav className={styles.nav} aria-label={t('a11y.mainNavigation')}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            >
              {t(item.titleKey)}
            </NavLink>
          ))}
        </nav>

        <div className={styles.actions}>
          <LanguageSwitch />
          <SoundToggle />
          <button type="button" className={styles.logout} onClick={logout}>
            <LogoutIcon />
            <span>{t('auth.logout')}</span>
          </button>
        </div>
      </header>

      <DemoBar />
      <SoundHint />

      <main className={styles.main} id="main" tabIndex={-1}>
        <Outlet />
      </main>

      <NewOrderWatcher />
      <NoticeBar />
    </div>
  );
}
