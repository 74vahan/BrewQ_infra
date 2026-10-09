import { useTranslation } from 'react-i18next';
import { DEFAULT_LANGUAGE, isLanguageCode } from './language.ts';
import type { LanguageCode } from './language.ts';

/** The interface language as one of the supported codes (for Intl formatting). */
export function useLanguage(): LanguageCode {
  const { i18n } = useTranslation();
  return isLanguageCode(i18n.resolvedLanguage) ? i18n.resolvedLanguage : DEFAULT_LANGUAGE;
}
