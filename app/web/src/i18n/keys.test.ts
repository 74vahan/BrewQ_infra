import { describe, expect, it } from 'vitest';
import { API_ERROR_CODES } from '../api/errorCodes.ts';
import { CATEGORIES, ORDER_STATUSES, SIZES } from '../api/types.ts';
import { actionKey, categoryKey, errorKey, sizeKey, statusKey } from './keys.ts';
import { matchLanguage } from './language.ts';
import en from './locales/en.json';
import hy from './locales/hy.json';
import ru from './locales/ru.json';

const LOCALES = { en, ru, hy } as const;

function lookup(dictionary: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((node, part) => {
    return typeof node === 'object' && node !== null ? (node as Record<string, unknown>)[part] : undefined;
  }, dictionary);
}

function expectTranslated(key: string): void {
  for (const [code, dictionary] of Object.entries(LOCALES)) {
    const value = lookup(dictionary, key);
    expect(typeof value === 'string' && value !== '', `${code}: ${key}`).toBe(true);
  }
}

describe('server-driven keys exist in every locale', () => {
  it.each(API_ERROR_CODES)('error %s', (code) => {
    expectTranslated(errorKey(code));
    expect(errorKey(code)).toBe(`errors.${code}`);
  });

  it.each(ORDER_STATUSES)('status %s', (status) => {
    expectTranslated(statusKey(status));
  });

  it.each(ORDER_STATUSES.filter((s) => s !== 'NEW'))('action %s', (status) => {
    const key = actionKey(status);
    expect(key).not.toBeNull();
    expectTranslated(key ?? '');
  });

  it.each(SIZES)('size %s', (size) => {
    expectTranslated(sizeKey(size));
  });

  it.each(CATEGORIES)('category %s', (category) => {
    expectTranslated(categoryKey(category));
  });
});

describe('unknown server values fall back to a neutral label', () => {
  it('uses the unknown keys', () => {
    expect(errorKey('SOMETHING_NEW')).toBe('errors.UNKNOWN');
    expect(statusKey('ARCHIVED')).toBe('status.unknown');
    expect(sizeKey('XL')).toBe('size.unknown');
    expect(categoryKey('soup')).toBe('category.unknown');
    expect(actionKey('NEW')).toBeNull();
    expect(actionKey('ARCHIVED')).toBeNull();
    for (const key of ['errors.UNKNOWN', 'status.unknown', 'size.unknown', 'category.unknown']) {
      expectTranslated(key);
    }
  });
});

describe('matchLanguage', () => {
  it('maps browser tags to supported codes', () => {
    expect(matchLanguage('ru-RU')).toBe('ru');
    expect(matchLanguage('hy')).toBe('hy');
    expect(matchLanguage('EN-us')).toBe('en');
    expect(matchLanguage('de-DE')).toBeNull();
    expect(matchLanguage(undefined)).toBeNull();
  });
});
