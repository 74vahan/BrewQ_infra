import { useTranslation } from 'react-i18next';
import { fakeControls, isFakeApi } from '../api/index.ts';
import styles from './DemoBar.module.css';

/**
 * Strip shown only with the fake data layer (never in a production build):
 * says the data is made up and lets a developer "place an order as a customer".
 * More levers (conflict, offline, 429, expired session) are on `window.brewqFake`.
 */
export function DemoBar() {
  const { t } = useTranslation();
  if (!isFakeApi) return null;

  return (
    <div className={styles.bar}>
      <p className={styles.text}>{t('dev.fakeApi')}</p>
      <button
        type="button"
        className={styles.button}
        onClick={() => {
          fakeControls?.addOrder();
        }}
      >
        {t('dev.addOrder')}
      </button>
    </div>
  );
}
