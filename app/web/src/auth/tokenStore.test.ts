import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearSession, getSession, getToken, isExpired, saveSession } from './tokenStore.ts';

function fakeStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => {
      data.clear();
    },
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => {
      data.delete(key);
    },
    setItem: (key, value) => {
      data.set(key, value);
    },
  };
}

const FUTURE = new Date(Date.now() + 3_600_000).toISOString();
const PAST = new Date(Date.now() - 1000).toISOString();

describe('tokenStore', () => {
  let storage: Storage;

  beforeEach(() => {
    storage = fakeStorage();
    vi.stubGlobal('localStorage', storage);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('round-trips a live session', () => {
    saveSession({ token: 't1', expiresAt: FUTURE });
    expect(getToken()).toBe('t1');
    expect(getSession()?.expiresAt).toBe(FUTURE);
  });

  it('treats an expired session as signed out', () => {
    saveSession({ token: 't1', expiresAt: PAST });
    expect(getToken()).toBeNull();
  });

  it('treats a malformed record as signed out', () => {
    storage.setItem('brewq.barista.session', '{not json');
    expect(getToken()).toBeNull();
    storage.setItem('brewq.barista.session', '{"token":"","expiresAt":"x"}');
    expect(getToken()).toBeNull();
  });

  it('clearSession removes the token and notifies nobody it cannot reach', () => {
    saveSession({ token: 't1', expiresAt: FUTURE });
    clearSession();
    expect(getToken()).toBeNull();
    expect(storage.getItem('brewq.barista.session')).toBeNull();
  });

  it('isExpired rejects unparsable dates', () => {
    expect(isExpired({ token: 't', expiresAt: 'garbage' })).toBe(true);
  });
});
