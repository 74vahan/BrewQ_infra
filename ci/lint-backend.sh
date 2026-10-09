#!/usr/bin/env bash
# Линтер и формат backend: ruff check + ruff format --check.
# Настройки — app/backend/pyproject.toml. Версия ruff закреплена в
# app/backend/requirements-dev.txt (в CI ставится оттуда же).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/app/backend"

if command -v ruff >/dev/null 2>&1; then
  RUFF=(ruff)
else
  RUFF=(python -m ruff)
fi

echo "==> ${RUFF[*]} --version: $("${RUFF[@]}" --version)"
echo "==> ruff check"
"${RUFF[@]}" check .
echo "==> ruff format --check"
"${RUFF[@]}" format --check .
echo "OK: backend lint passed"
