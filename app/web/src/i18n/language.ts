export const LANGUAGE_CODES = ['en', 'ru', 'hy'] as const;
export type LanguageCode = (typeof LANGUAGE_CODES)[number];

export const DEFAULT_LANGUAGE: LanguageCode = 'en';
const STORAGE_KEY = 'brewq.language';

export function isLanguageCode(value: unknown): value is LanguageCode {
  return typeof value === 'string' && (LANGUAGE_CODES as readonly string[]).includes(value);
}

/** Maps a BCP 47 tag such as "ru-RU" to a supported code, or null. */
export function matchLanguage(tag: string | undefined): LanguageCode | null {
  const base = tag?.slice(0, 2).toLowerCase();
  return isLanguageCode(base) ? base : null;
}

export function readStoredLanguage(): LanguageCode | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isLanguageCode(stored) ? stored : null;
  } catch {
    return null; // Private mode or blocked storage.
  }
}

export function storeLanguage(code: LanguageCode): void {
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // Not being able to remember the choice must not break the UI.
  }
}

/** Saved choice, else the browser language, else English. */
export function detectLanguage(): LanguageCode {
  return readStoredLanguage() ?? matchLanguage(navigator.language) ?? DEFAULT_LANGUAGE;
}
