import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { DEFAULT_LANGUAGE, detectLanguage, isLanguageCode, storeLanguage } from './language.ts';
import en from './locales/en.json';
import hy from './locales/hy.json';
import ru from './locales/ru.json';

/** Keeps <html lang> in step with the interface language (the tab title is <DocumentTitle>'s job). */
function syncDocument(language: string): void {
  document.documentElement.lang = language;
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
    hy: { translation: hy },
  },
  lng: detectLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: ['en', 'ru', 'hy'],
  initAsync: false,
  interpolation: { escapeValue: false }, // React already escapes.
});

i18n.on('languageChanged', syncDocument);
syncDocument(i18n.language);

export function changeLanguage(code: string): void {
  if (!isLanguageCode(code)) return;
  storeLanguage(code);
  void i18n.changeLanguage(code);
}

export default i18n;
