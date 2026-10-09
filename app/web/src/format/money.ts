import type { LanguageCode } from '../i18n/language.ts';

/** Intl locale per interface language (the amount grouping follows it). */
const INTL_LOCALE: Record<LanguageCode, string> = {
  en: 'en-US',
  ru: 'ru-RU',
  hy: 'hy-AM',
};

/** Whole AMD amount ("*_amd" fields are integers) in the grouping and currency style of the locale. */
export function formatAmd(amount: number, language: LanguageCode): string {
  return new Intl.NumberFormat(INTL_LOCALE[language], {
    style: 'currency',
    currency: 'AMD',
    maximumFractionDigits: 0,
  }).format(amount);
}
