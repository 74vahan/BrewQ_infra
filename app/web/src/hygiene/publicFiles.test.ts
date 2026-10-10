import { describe, expect, it } from 'vitest';
import indexHtml from '../../index.html?raw';
import privacyEn from '../../privacy.html?raw';
import privacyHy from '../../privacy.hy.html?raw';
import privacyRu from '../../privacy.ru.html?raw';
import robots from '../../public/robots.txt?raw';
import manifestSource from '../../public/site.webmanifest?raw';

/** Static files the panel ships next to the app (R7). */
const publicFiles = Object.keys(import.meta.glob('../../public/*', { query: '?url', import: 'default' })).map((path) =>
  path.replace('../../public/', ''),
);

describe('index.html', () => {
  it('has one description, noindex and the icon / manifest links', () => {
    expect(indexHtml.match(/<meta name="description"/g)).toHaveLength(1);
    expect(indexHtml).toContain('<meta name="robots" content="noindex, nofollow"');
    expect(indexHtml).toContain('rel="manifest" href="/site.webmanifest"');
    expect(indexHtml).toContain('rel="apple-touch-icon" href="/apple-touch-icon.png"');
    expect(indexHtml).toContain('href="/favicon.svg"');
    expect(indexHtml).toContain('href="/favicon-32.png"');
  });

  it('sets a theme colour for both colour schemes', () => {
    expect(indexHtml).toMatch(/name="theme-color" content="#[0-9a-f]{6}" media="\(prefers-color-scheme: dark\)"/);
    expect(indexHtml).toMatch(/name="theme-color" content="#[0-9a-f]{6}" media="\(prefers-color-scheme: light\)"/);
  });
});

describe('public files', () => {
  it('keeps crawlers out of the panel', () => {
    expect(robots).toMatch(/^User-agent: \*\s*$/m);
    expect(robots).toMatch(/^Disallow: \/\s*$/m);
  });

  it('has a manifest whose icons exist', () => {
    const manifest = JSON.parse(manifestSource) as {
      name: string;
      theme_color: string;
      icons: { src: string; sizes: string }[];
    };
    expect(manifest.name).not.toBe('');
    expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/);
    expect(manifest.icons.map((icon) => icon.sizes).sort()).toEqual(['192x192', '512x512']);
    for (const icon of manifest.icons) expect(publicFiles, icon.src).toContain(icon.src.slice(1));
  });

  it('has the favicon set', () => {
    for (const file of ['favicon.svg', 'favicon-32.png', 'apple-touch-icon.png', 'icon-192.png', 'icon-512.png']) {
      expect(publicFiles, file).toContain(file);
    }
  });
});

describe.each([
  ['privacy.html', 'en', privacyEn],
  ['privacy.ru.html', 'ru', privacyRu],
  ['privacy.hy.html', 'hy', privacyHy],
])('%s', (_file, language, html) => {
  it('is a public, script-free page in its language', () => {
    expect(html).toContain(`<html lang="${language}">`);
    expect(html).not.toMatch(/<script/i);
    expect(html).not.toMatch(/<style|style=/i); // the CSP allows no inline styles
    expect(html).not.toContain('noindex');
  });

  it('links to all three language versions', () => {
    for (const target of ['/privacy.html', '/privacy.ru.html', '/privacy.hy.html']) {
      expect(html).toContain(`href="${target}"`);
    }
  });

  it('points to no external resources (CSP: everything from our own origin)', () => {
    expect(html).not.toMatch(/(src|href)="https?:\/\//);
  });
});
