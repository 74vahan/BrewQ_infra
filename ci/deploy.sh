#!/usr/bin/env bash
# Деплой на сервер по SSH: кладёт готовые архивы (их собирает build-bundle.sh)
# в $APP_ROOT/.incoming и запускает remote-deploy.sh на сервере.
#
# Используется workflow'ом и запускается руками:
#   SERVER_HOST=1.2.3.4 SSH_KEY=~/.ssh/brewq RELEASE_SHA=$(git rev-parse --short HEAD) ci/deploy.sh
#
# Чего этот скрипт НЕ делает: не создаёт и не меняет /srv/brewq/.env. Файл пишет
# один раз bootstrap из BrewQ_image; если деплой выдумает новые пароли, том MySQL
# и backend разойдутся, а токены баристы перестанут действовать.
#
# Переменные:
#   SERVER_HOST (обяз.), SSH_KEY — путь к приватному ключу (обяз.)
#   SERVER_USER (brewq), APP_ROOT (/srv/brewq), RELEASE_SHA (git rev-parse), KEEP_RELEASES (5)
#   SSH_KNOWN_HOSTS — содержимое known_hosts; без него StrictHostKeyChecking=accept-new
#   BUNDLE_DIR      — где лежат app.tar.gz и web.tar.gz (по умолчанию <repo>/build/bundle)
set -euo pipefail

SERVER_HOST="${SERVER_HOST:?SERVER_HOST is required}"
SERVER_USER="${SERVER_USER:-brewq}"
SSH_KEY="${SSH_KEY:?SSH_KEY (path to the private key) is required}"
APP_ROOT="${APP_ROOT:-/srv/brewq}"
RELEASE_SHA="${RELEASE_SHA:-$(git rev-parse --short HEAD 2>/dev/null || true)}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${BUNDLE_DIR:-${REPO_ROOT}/build/bundle}"

# Значения попадают в строку, выполняемую удалённым shell'ом, поэтому
# проверяются жёстко: никаких кавычек, пробелов и подстановок.
[[ "$APP_ROOT" =~ ^/[A-Za-z0-9_./-]+$ ]] || { echo "Invalid APP_ROOT: ${APP_ROOT}" >&2; exit 1; }
[[ "$RELEASE_SHA" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid or empty RELEASE_SHA: '${RELEASE_SHA}'" >&2; exit 1; }
[[ "$KEEP_RELEASES" =~ ^[1-9][0-9]*$ ]] || { echo "KEEP_RELEASES must be a number >= 1" >&2; exit 1; }
[[ "$SERVER_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "Invalid SERVER_USER" >&2; exit 1; }
[[ "$SERVER_HOST" =~ ^[A-Za-z0-9._:-]+$ ]] || { echo "Invalid SERVER_HOST" >&2; exit 1; }

if [ ! -f "${BUNDLE_DIR}/app.tar.gz" ] || [ ! -f "${BUNDLE_DIR}/web.tar.gz" ]; then
  echo "No bundle in ${BUNDLE_DIR} - run ci/build-bundle.sh first" >&2
  exit 1
fi
[ -f "$SSH_KEY" ] || { echo "SSH key not found: ${SSH_KEY}" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SSH_OPTS=(-i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
# Настоящий known_hosts закрывает окно MITM при первом подключении. Без секрета
# соединение всё равно идёт, но с явным предупреждением.
if [ -n "${SSH_KNOWN_HOSTS:-}" ]; then
  printf '%s\n' "$SSH_KNOWN_HOSTS" > "${TMP}/known_hosts"
  SSH_OPTS+=(-o "UserKnownHostsFile=${TMP}/known_hosts" -o StrictHostKeyChecking=yes)
else
  echo "==> WARNING: SSH_KNOWN_HOSTS is not set, trusting the host on first use"
  SSH_OPTS+=(-o StrictHostKeyChecking=accept-new)
fi
TARGET="${SERVER_USER}@${SERVER_HOST}"
INCOMING="${APP_ROOT}/.incoming"

echo "==> Preparing ${TARGET}:${INCOMING}"
# Значения проверены выше; подстановка на стороне клиента намеренна.
# shellcheck disable=SC2029
ssh "${SSH_OPTS[@]}" "$TARGET" "mkdir -p '${INCOMING}' && chmod 700 '${INCOMING}'"

echo "==> Copying the bundle"
scp "${SSH_OPTS[@]}" "${BUNDLE_DIR}/app.tar.gz" "${BUNDLE_DIR}/web.tar.gz" "${TARGET}:${INCOMING}/"

echo "==> Deploying release ${RELEASE_SHA}"
# shellcheck disable=SC2029
ssh "${SSH_OPTS[@]}" "$TARGET" \
  "APP_ROOT='${APP_ROOT}' RELEASE_SHA='${RELEASE_SHA}' KEEP_RELEASES='${KEEP_RELEASES}' bash -s" \
  < "${REPO_ROOT}/ci/remote-deploy.sh"

echo "==> Deployed release ${RELEASE_SHA} to ${SERVER_HOST}"
