import { describe, expect, it } from 'vitest';

/** Source-level rules of the panel that a browser check would only find late. */
const components = import.meta.glob<string>('../**/*.tsx', { query: '?raw', import: 'default', eager: true });
const styles = import.meta.glob<string>('../**/*.css', { query: '?raw', import: 'default', eager: true });
const scripts = import.meta.glob<string>(['../**/*.ts', '!../**/*.test.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

const offenders = (files: Record<string, string>, bad: (text: string) => boolean): string[] =>
  Object.entries(files)
    .filter(([, text]) => bad(text))
    .map(([path]) => path);

describe('scanner', () => {
  it('actually sees the sources (the rules below would pass on nothing)', () => {
    expect(Object.keys(components).length).toBeGreaterThan(20);
    expect(Object.keys(styles).length).toBeGreaterThan(20);
    expect(Object.keys(scripts).length).toBeGreaterThan(20);
  });
});

describe('accessibility of images', () => {
  it('every <img> in the app has an alt attribute (alt="" only for decorative pictures)', () => {
    const missing = offenders(components, (text) =>
      [...text.matchAll(/<img\b[^>]*>/g)].some((tag) => !/\balt=/.test(tag[0])),
    );
    expect(missing).toEqual([]);
  });
});

describe('fonts', () => {
  const fontsCss = Object.entries(styles).find(([path]) => path.endsWith('/styles/fonts.css'))?.[1] ?? '';

  it('declares the same weight range on every BrewQ Sans face (otherwise unicode-range skips some faces)', () => {
    const ranges = [...fontsCss.matchAll(/font-weight:\s*([^;]+);/g)].map((match) => match[1]);
    expect(ranges).toHaveLength(4);
    expect(new Set(ranges).size).toBe(1);
  });

  it('bundles Sora for Latin and serves every font file from node_modules (no CDN)', () => {
    expect(fontsCss).toContain('@fontsource-variable/sora/files/sora-latin-wght-normal.woff2');
    for (const [, url] of fontsCss.matchAll(/url\('([^']+)'\)/g)) expect(url).toMatch(/^@fontsource-variable\//);
  });
});

describe('CSP friendliness', () => {
  it('uses no inline styles in components', () => {
    expect(offenders(components, (text) => /\sstyle=\{/.test(text) || /<style[\s>]/.test(text))).toEqual([]);
  });

  it('loads no fonts or stylesheets from the internet', () => {
    const external = (text: string): boolean =>
      /url\(\s*['"]?https?:/.test(text) || /@import\s+(url\()?['"]?https?:/.test(text);
    expect(offenders({ ...styles, ...components, ...scripts }, external)).toEqual([]);
  });
});
