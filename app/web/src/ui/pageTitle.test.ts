import { describe, expect, it } from 'vitest';
import en from '../i18n/locales/en.json';
import hy from '../i18n/locales/hy.json';
import ru from '../i18n/locales/ru.json';
import { composeTitle, titleKeyFor } from './pageTitle.ts';

describe('titleKeyFor', () => {
  it('names every screen of the panel', () => {
    expect(titleKeyFor('/')).toBe('queue.title');
    expect(titleKeyFor('/today')).toBe('today.title');
    expect(titleKeyFor('/menu')).toBe('menu.title');
    expect(titleKeyFor('/login')).toBe('auth.title');
  });

  it('ignores trailing slashes, as the router does', () => {
    expect(titleKeyFor('/today/')).toBe('today.title');
  });

  it('falls back to the not-found title for anything else', () => {
    expect(titleKeyFor('/nope')).toBe('notFound.title');
    expect(titleKeyFor('/today/extra')).toBe('notFound.title');
  });

  it.each([
    ['en', en],
    ['ru', ru],
    ['hy', hy],
  ])('has a translated page name for every route in %s', (_code, dictionary) => {
    for (const path of ['/', '/today', '/menu', '/login', '/missing']) {
      const [section, key] = titleKeyFor(path).split('.') as [keyof typeof dictionary, string];
      const value = (dictionary[section] as Record<string, string>)[key];
      expect(typeof value === 'string' && value !== '').toBe(true);
    }
  });
});

describe('composeTitle', () => {
  it('joins the page and the app name', () => {
    expect(composeTitle('Queue', 'BrewQ', 0)).toBe('Queue · BrewQ');
  });

  it('puts the number of unseen orders in front', () => {
    expect(composeTitle('Queue', 'BrewQ', 2)).toBe('(2) Queue · BrewQ');
  });
});
