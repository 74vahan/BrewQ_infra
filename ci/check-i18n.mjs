#!/usr/bin/env node
/**
 * i18n parity check for the barista panel (memory/05-ci-cd.md).
 *
 * Lives in ci/ (run by CI and by `npm run check:i18n` in app/web). Paths
 * default to the repo layout and can be overridden:
 *   node ci/check-i18n.mjs [localesDir] [srcDir]
 *
 * Fails (exit 1) when:
 *   1. a locale has a key the English file lacks, or lacks one English has;
 *   2. a value is not a non-empty string;
 *   3. {{placeholders}} differ between a locale and English for the same key;
 *   4. code uses a literal key (t('a.b') or *Key="a.b") that English lacks.
 *      Dynamic keys (errors.${code}) are covered by src/i18n/keys.test.ts.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..');
const localesDir = resolve(process.argv[2] ?? join(repoRoot, 'app', 'web', 'src', 'i18n', 'locales'));
const srcDir = resolve(process.argv[3] ?? join(repoRoot, 'app', 'web', 'src'));
const LANGUAGES = ['en', 'ru', 'hy'];
const BASE = 'en';

const problems = [];

function flatten(node, prefix = '', out = new Map()) {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      flatten(value, path, out);
    } else {
      out.set(path, value);
    }
  }
  return out;
}

const placeholders = (text) => [...text.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map((m) => m[1]).sort().join(',');

const dictionaries = {};
for (const language of LANGUAGES) {
  const file = join(localesDir, `${language}.json`);
  try {
    dictionaries[language] = flatten(JSON.parse(readFileSync(file, 'utf8')));
  } catch (error) {
    problems.push(`${language}.json: cannot read/parse (${error.message})`);
  }
}

const base = dictionaries[BASE];
if (base) {
  for (const language of LANGUAGES) {
    const dictionary = dictionaries[language];
    if (!dictionary) continue;

    for (const [key, value] of dictionary) {
      if (typeof value !== 'string' || value.trim() === '') {
        problems.push(`${language}.json: "${key}" is not a non-empty string`);
      }
    }
    if (language === BASE) continue;

    for (const key of base.keys()) {
      if (!dictionary.has(key)) problems.push(`${language}.json: missing key "${key}"`);
    }
    for (const key of dictionary.keys()) {
      if (!base.has(key)) problems.push(`${language}.json: extra key "${key}" (not in ${BASE}.json)`);
    }
    for (const [key, value] of dictionary) {
      const baseValue = base.get(key);
      if (typeof value === 'string' && typeof baseValue === 'string' && placeholders(value) !== placeholders(baseValue)) {
        problems.push(`${language}.json: "${key}" placeholders differ from ${BASE}.json`);
      }
    }
  }

  // Literal keys used in source must exist.
  const files = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name)) files.push(full);
    }
  };
  walk(srcDir);

  const used = /(?:\bt\(\s*|\b\w*Key\s*[=:]\s*)['"]([A-Za-z][\w]*(?:\.[\w]+)+)['"]/g;
  for (const file of files) {
    const text = readFileSync(file, 'utf8');
    for (const match of text.matchAll(used)) {
      if (!base.has(match[1])) problems.push(`${file.slice(srcDir.length + 1)}: unknown i18n key "${match[1]}"`);
    }
  }
}

if (problems.length > 0) {
  console.error(`i18n check FAILED (${problems.length}):`);
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}
console.log(`i18n check OK: ${base ? base.size : 0} keys x ${LANGUAGES.length} languages`);
