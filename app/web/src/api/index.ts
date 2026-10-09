import { httpBaristaApi } from './barista.ts';
import type { BaristaApi } from './barista.ts';
import type { FakeControls } from './fake/controls.ts';
import { createFakeBackend } from './fake/fakeBarista.ts';

/**
 * Picks the data layer once at startup.
 *
 * - Production build: always the real HTTP client (`import.meta.env.DEV` is
 *   statically false, so the fake layer is dropped from the bundle).
 * - `npm run dev`: the in-memory fake until the backend is up; set
 *   `VITE_USE_FAKE_API=false` to go through the dev proxy to the real one.
 */
const useFake = import.meta.env.DEV && import.meta.env.VITE_USE_FAKE_API !== 'false';

const fakeBackend = useFake ? createFakeBackend(import.meta.env.VITE_FAKE_API_PASSWORD ?? '') : null;

export const baristaApi: BaristaApi = fakeBackend?.api ?? httpBaristaApi;

export const isFakeApi: boolean = useFake;

/** Levers of the fake backend (demo button, `window.brewqFake`); null with the real API. */
export const fakeControls: FakeControls | null = fakeBackend?.controls ?? null;

if (fakeControls && typeof window !== 'undefined') {
  (window as unknown as { brewqFake?: FakeControls }).brewqFake = fakeControls;
}
