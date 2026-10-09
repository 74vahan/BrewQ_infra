import { useTranslation } from 'react-i18next';
import { changeLanguage } from '../i18n/index.ts';
import { LANGUAGE_CODES } from '../i18n/language.ts';
import styles from './LanguageSwitch.module.css';

/** EN / RU / HY segmented control; the choice is remembered in localStorage. */
export function LanguageSwitch() {
  const { t, i18n } = useTranslation();

  return (
    <div className={styles.group} role="group" aria-label={t('language.label')}>
      {LANGUAGE_CODES.map((code) => (
        <button
          key={code}
          type="button"
          className={styles.option}
          lang={code}
          aria-pressed={i18n.resolvedLanguage === code}
          aria-label={t('language.native', { lng: code })}
          title={t('language.native', { lng: code })}
          onClick={() => {
            changeLanguage(code);
          }}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
