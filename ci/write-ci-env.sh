#!/usr/bin/env bash
# Пишет ВРЕМЕННЫЙ .env для CI: compose требует обязательные переменные
# (${VAR:?...}), а настоящий /srv/brewq/.env в CI не существует.
#
# Пароли генерируются случайно при каждом запуске и нигде не сохраняются, так
# что в репозитории нет даже тестовых паролей (правило №9).
#
#   ci/write-ci-env.sh <файл>            # BACKEND_PORT берётся из окружения (по умолчанию 8081)
set -euo pipefail

OUT="${1:?usage: write-ci-env.sh <output file>}"
PORT="${BACKEND_PORT:-8081}"

# hex без спецсимволов: значения идут в DATABASE_URL без экранирования.
# od вместо `tr </dev/urandom | head`, чтобы не ловить SIGPIPE под pipefail.
rand() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }

umask 077
{
  echo "MYSQL_DATABASE=brewq"
  echo "MYSQL_USER=brewq"
  echo "MYSQL_PASSWORD=$(rand 16)"
  echo "MYSQL_ROOT_PASSWORD=$(rand 16)"
  echo "BARISTA_PASSWORD=$(rand 12)"
  echo "BARISTA_TOKEN_SECRET=$(rand 32)"
  echo "BARISTA_TOKEN_TTL_HOURS=12"
  echo "BACKEND_PORT=${PORT}"
  echo "PUBLIC_BASE_URL=http://127.0.0.1:${PORT}"
  echo "LOG_LEVEL=INFO"
} > "$OUT"

echo "Wrote a throw-away CI env file: ${OUT}"
