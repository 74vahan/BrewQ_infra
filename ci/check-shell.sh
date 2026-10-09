#!/usr/bin/env bash
# bash -n (синтаксис) и shellcheck по ci/*.sh. Запуск из любого места.
# Нет shellcheck локально — шаг пропускается с предупреждением; в CI
# REQUIRE_SHELLCHECK=1 превращает его отсутствие в ошибку.
set -euo pipefail

CI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scripts=("${CI_DIR}"/*.sh)

for script in "${scripts[@]}"; do
  bash -n "$script"
done
echo "OK: bash -n passed for ${#scripts[@]} scripts"

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck "${scripts[@]}"
  echo "OK: shellcheck passed"
elif [ "${REQUIRE_SHELLCHECK:-0}" = "1" ]; then
  echo "shellcheck is required but not installed" >&2
  exit 1
else
  echo "WARNING: shellcheck is not installed, skipped"
fi
