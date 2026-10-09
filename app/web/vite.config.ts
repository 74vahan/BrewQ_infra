/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { createReadStream, statSync } from 'node:fs';
import { extname, resolve, sep } from 'node:path';
import { defineConfig } from 'vite';
import type { Plugin } from 'vite';

// In production nginx serves the built files and proxies /api and /media to
// the backend on the same origin, so the app always uses relative URLs. In
// development Vite proxies them to the backend published by docker compose.
const API_TARGET = process.env['VITE_API_TARGET'] ?? 'http://127.0.0.1:8081';

const MEDIA_ROOT = resolve(import.meta.dirname, '..', 'media');
const MEDIA_TYPES: Record<string, string> = {
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
};

/**
 * Dev only: serves the menu pictures from app/media (the folder nginx serves
 * as /media/ in production) so they show without a backend. A file that is not
 * there falls through to the proxy below.
 */
function devMedia(): Plugin {
  return {
    name: 'brewq-dev-media',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/media', (req, res, next) => {
        const requested = resolve(MEDIA_ROOT, '.' + decodeURIComponent((req.url ?? '/').split('?')[0] ?? '/'));
        const type = MEDIA_TYPES[extname(requested).toLowerCase()];
        if (!type || !requested.startsWith(MEDIA_ROOT + sep)) return next();
        try {
          if (!statSync(requested).isFile()) return next();
        } catch {
          return next();
        }
        res.setHeader('Content-Type', type);
        createReadStream(requested).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), devMedia()],

  server: {
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/media': { target: API_TARGET, changeOrigin: true },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: false,
  },

  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
