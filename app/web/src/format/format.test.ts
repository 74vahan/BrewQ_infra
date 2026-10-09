import { describe, expect, it } from 'vitest';
import { formatAmd } from './money.ts';
import { minutesSince } from './time.ts';

describe('formatAmd', () => {
  it('formats whole dram without decimals in every language', () => {
    for (const language of ['en', 'ru', 'hy'] as const) {
      const text = formatAmd(1300, language);
      expect(text).toMatch(/1\D?300/);
      expect(text).not.toMatch(/[.,]\d{2}$/);
    }
  });
});

describe('minutesSince', () => {
  const now = Date.parse('2026-10-09T10:00:00Z');

  it('counts whole minutes', () => {
    expect(minutesSince('2026-10-09T09:55:30Z', now)).toBe(4);
  });

  it('never goes negative (clock skew) and tolerates bad input', () => {
    expect(minutesSince('2026-10-09T10:05:00Z', now)).toBe(0);
    expect(minutesSince('garbage', now)).toBe(0);
  });
});
