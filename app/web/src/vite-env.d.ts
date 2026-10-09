/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Dev only: "false" switches `npm run dev` from the fake data layer to the real backend. */
  readonly VITE_USE_FAKE_API?: string;
  /** Dev only: password accepted by the fake login (empty = any non-empty password). */
  readonly VITE_FAKE_API_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
