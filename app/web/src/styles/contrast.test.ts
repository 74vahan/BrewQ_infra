import { describe, expect, it } from 'vitest';
import { contrast, over, parseHex } from './contrastMath.ts';
import type { Rgb } from './contrastMath.ts';
import { parseThemes } from './tokens.ts';
import type { TokenSet } from './tokens.ts';
import tokensCss from './tokens.css?raw';

const themes = parseThemes(tokensCss);

const hex = (tokens: TokenSet, name: string): Rgb => {
  const value = tokens[name];
  if (!value) throw new Error(`Missing token ${name}`);
  return parseHex(value);
};

/** The 10% wash of the status colour behind the status chip (StatusChip.module.css). */
const chipBackground = (tokens: TokenSet, colour: string, page: string): Rgb =>
  over(hex(tokens, colour), hex(tokens, page), 0.1);

/** text, background, minimum ratio. Names are tokens from tokens.css. */
const TEXT_PAIRS: [string, string, number][] = [
  ['--text', '--bg', 4.5],
  ['--text', '--surface', 4.5],
  ['--text', '--surface-raised', 4.5],
  ['--text', '--accent-soft', 4.5],
  ['--text-muted', '--bg', 4.5],
  ['--text-muted', '--surface', 4.5],
  ['--text-muted', '--surface-raised', 4.5],
  ['--accent-strong', '--bg', 4.5],
  ['--accent-strong', '--surface', 4.5],
  ['--accent-ink-small', '--accent', 4.5],
  ['--accent-ink', '--accent', 3], // large bold text only (buttons: 19px / 700)
  ['--chrome-text', '--chrome-bg', 4.5],
  ['--chrome-text', '--chrome-raised', 4.5],
  ['--chrome-muted', '--chrome-bg', 4.5],
  ['--chrome-accent', '--chrome-bg', 4.5],
  ['--status-new', '--bg', 4.5],
  ['--status-new', '--surface', 4.5],
  ['--status-progress', '--bg', 4.5],
  ['--status-progress', '--surface', 4.5],
  ['--status-ready', '--bg', 4.5],
  ['--status-ready', '--surface', 4.5],
  ['--danger', '--bg', 4.5],
  ['--danger', '--surface', 4.5],
  ['--danger-ink', '--danger', 4.5],
];

/** Non-text parts that must stay visible: control borders, switch track, focus ring. */
const GRAPHIC_PAIRS: [string, string, number][] = [
  ['--control-border', '--bg', 3],
  ['--control-border', '--surface', 3],
  ['--control-border', '--surface-raised', 3],
  ['--accent', '--surface', 3],
  ['--focus', '--bg', 3],
  ['--focus', '--surface', 3],
];

for (const [themeName, tokens] of Object.entries(themes)) {
  describe(`${themeName} theme`, () => {
    it.each(TEXT_PAIRS)('%s on %s is at least %d:1', (foreground, background, minimum) => {
      expect(contrast(hex(tokens, foreground), hex(tokens, background))).toBeGreaterThanOrEqual(minimum);
    });

    it.each(GRAPHIC_PAIRS)('%s against %s is at least %d:1', (foreground, background, minimum) => {
      expect(contrast(hex(tokens, foreground), hex(tokens, background))).toBeGreaterThanOrEqual(minimum);
    });

    it.each(['--status-new', '--status-progress', '--status-ready', '--danger'])(
      '%s stays readable on its own tinted chip, on the page and on a card',
      (colour) => {
        for (const page of ['--bg', '--surface']) {
          expect(contrast(hex(tokens, colour), chipBackground(tokens, colour, page))).toBeGreaterThanOrEqual(4.5);
        }
      },
    );

    it('keeps the muted status colour (picked up) readable on its chip', () => {
      for (const page of ['--bg', '--surface']) {
        const wash = over(hex(tokens, '--text-muted'), hex(tokens, page), 0.1);
        expect(contrast(hex(tokens, '--text-muted'), wash)).toBeGreaterThanOrEqual(4.5);
      }
    });
  });
}

describe('contrast helpers', () => {
  it('matches the WCAG reference values', () => {
    expect(contrast(parseHex('#000000'), parseHex('#ffffff'))).toBeCloseTo(21, 5);
    expect(contrast(parseHex('#777777'), parseHex('#ffffff'))).toBeCloseTo(4.48, 1);
  });

  it('blends a colour over another', () => {
    expect(over(parseHex('#ffffff'), parseHex('#000000'), 0.5)).toEqual([128, 128, 128]);
  });

  it('parses the theme blocks', () => {
    expect(themes.dark['--bg']).toBe('#1f1f1f');
    expect(themes.light['--bg']).toBe('#f9f2ed');
    expect(themes.light['--accent']).toBe('#c67c4e'); // inherited from the dark block, not redefined
  });
});
