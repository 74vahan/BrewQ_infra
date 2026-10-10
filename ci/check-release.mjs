#!/usr/bin/env node
/**
 * Pre-release check (run by hand: `npm run check:release` in app/web).
 * Fails while a TODO(user) placeholder is still left in the public privacy
 * pages. Deliberately NOT part of `npm test` or CI: the placeholders are
 * legitimate until the owner fills in the real data.
 */
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'app', 'web');
const files = ['privacy.html', 'privacy.ru.html', 'privacy.hy.html'];

let left = 0;
for (const file of files) {
  const count = (readFileSync(join(webDir, file), 'utf8').match(/TODO\(user\)/g) ?? []).length;
  if (count > 0) console.error(`${file}: ${count} TODO(user) placeholder(s) left`);
  left += count;
}

if (left > 0) {
  console.error('check:release FAILED: fill in the placeholders before releasing.');
  process.exit(1);
}
console.log('check:release OK: no TODO(user) placeholders in the privacy pages');
