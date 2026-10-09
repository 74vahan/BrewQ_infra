#!/usr/bin/env bash
# Выполняется НА СЕРВЕРЕ: deploy.sh подаёт его в `bash -s` по ssh. Руками локально
# не запускать (кроме проверки на каталоге-имитации, см. memory/05-ci-cd.md).
#
# Раскладка создаётся bootstrap'ом из BrewQ_image:
#   /srv/brewq/.env                  пишется один раз, режим 600, здесь только читается
#   /srv/brewq/app/                  заменяется этим скриптом (backend/ docker/ media/)
#   /srv/brewq/web/releases/<sha>/   по каталогу на релиз
#   /srv/brewq/web/current           симлинк, переключается атомарно
#   /srv/brewq/.incoming/            сюда deploy.sh кладёт app.tar.gz и web.tar.gz
#
# nginx работает на хосте и читает web/current и app/media; в деплой он не входит.
# sudo не нужен: пользователь brewq владеет /srv/brewq и состоит в группе docker.
#
# Переменные: APP_ROOT (/srv/brewq), RELEASE_SHA (обяз.), KEEP_RELEASES (5),
# READY_TIMEOUT (120), INCOMING_DIR ($APP_ROOT/.incoming), BACKEND_PORT
# (из .env, иначе 8081), HEALTH_URL (по умолчанию http://127.0.0.1:<порт>/api/health/ready).
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/brewq}"
RELEASE_SHA="${RELEASE_SHA:?RELEASE_SHA is required}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
READY_TIMEOUT="${READY_TIMEOUT:-120}"

ENV_FILE="${APP_ROOT}/.env"
APP_DIR="${APP_ROOT}/app"
WEB_DIR="${APP_ROOT}/web"
RELEASE_DIR="${WEB_DIR}/releases/${RELEASE_SHA}"
INCOMING_DIR="${INCOMING_DIR:-${APP_ROOT}/.incoming}"

[[ "$RELEASE_SHA" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid RELEASE_SHA: ${RELEASE_SHA}" >&2; exit 1; }
[[ "$KEEP_RELEASES" =~ ^[1-9][0-9]*$ ]] || { echo "KEEP_RELEASES must be a number >= 1" >&2; exit 1; }

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing ${ENV_FILE}." >&2
  echo "It is written once by the bootstrap script from BrewQ_image (terraform apply)" >&2
  echo "and must survive deploys. Refusing to invent secrets: the MySQL volume would" >&2
  echo "stop matching the backend and every barista token would be invalidated." >&2
  exit 1
fi
for archive in app.tar.gz web.tar.gz; do
  [ -f "${INCOMING_DIR}/${archive}" ] || { echo "Missing ${INCOMING_DIR}/${archive}" >&2; exit 1; }
done

# Два деплоя одновременно (CI и ручной запуск) испортили бы каталоги.
if command -v flock >/dev/null 2>&1; then
  exec 9> "${APP_ROOT}/.deploy.lock"
  flock -n 9 || { echo "Another deploy is already running" >&2; exit 1; }
fi

# Порт: переменная окружения, затем BACKEND_PORT из .env (читаем строку, а не
# source'им файл, чтобы не исполнять его как код), затем 8081.
if [ -z "${BACKEND_PORT:-}" ]; then
  BACKEND_PORT="$(sed -n 's/^BACKEND_PORT=//p' "$ENV_FILE" | tail -n 1 | tr -d '"\r ' || true)"
fi
BACKEND_PORT="${BACKEND_PORT:-8081}"
[[ "$BACKEND_PORT" =~ ^[0-9]+$ ]] || { echo "Invalid BACKEND_PORT: ${BACKEND_PORT}" >&2; exit 1; }
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${BACKEND_PORT}/api/health/ready}"

# </dev/null везде, где команда могла бы читать stdin: сам скрипт приходит в
# `bash -s` через stdin, и проглоченные строки сломали бы выполнение.
compose() {
  BACKEND_CONTEXT="${APP_DIR}/backend" docker compose -p brewq --env-file "$ENV_FILE" \
    -f "${APP_DIR}/docker/docker-compose.yml" "$@" < /dev/null
}

echo "==> Unpacking the application into ${APP_DIR}"
rm -rf "${APP_DIR}.new"
mkdir -p "${APP_DIR}.new"
tar -xzmf "${INCOMING_DIR}/app.tar.gz" -C "${APP_DIR}.new"
for required in backend/requirements.txt docker/docker-compose.yml docker/backend.Dockerfile media/menu; do
  [ -e "${APP_DIR}.new/${required}" ] || { echo "app.tar.gz is malformed: no ${required}" >&2; exit 1; }
done
rm -rf "${APP_DIR}.old"
if [ -d "$APP_DIR" ]; then mv "$APP_DIR" "${APP_DIR}.old"; fi
mv "${APP_DIR}.new" "$APP_DIR"
# app.old остаётся до успешной проверки готовности: при провале по нему видно,
# что работало раньше.

echo "==> Starting the stack"
compose up -d --build --remove-orphans

echo "==> Waiting for the API (${HEALTH_URL}, up to ${READY_TIMEOUT}s)"
deadline=$((SECONDS + READY_TIMEOUT))
until curl -fsS --max-time 5 "$HEALTH_URL" > /dev/null 2>&1 < /dev/null; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "The API did not become ready within ${READY_TIMEOUT}s. Recent logs:" >&2
    compose logs --tail 50 api >&2 || true
    echo "The panel was NOT switched. The previous app directory is kept as ${APP_DIR}.old." >&2
    exit 1
  fi
  sleep 3
done
echo "==> API is ready"
rm -rf "${APP_DIR}.old"

echo "==> Publishing the panel as release ${RELEASE_SHA}"
mkdir -p "${WEB_DIR}/releases"
rm -rf "${RELEASE_DIR}.tmp" "$RELEASE_DIR"
mkdir -p "${RELEASE_DIR}.tmp"
tar -xzmf "${INCOMING_DIR}/web.tar.gz" -C "${RELEASE_DIR}.tmp"
[ -f "${RELEASE_DIR}.tmp/index.html" ] || { echo "web.tar.gz has no index.html" >&2; exit 1; }
mv "${RELEASE_DIR}.tmp" "$RELEASE_DIR"
touch "$RELEASE_DIR"   # порядок чистки идёт по времени изменения каталога

# Атомарное переключение: `ln -sfn` поверх живого симлинка неатомарен, а rename
# одного симлинка поверх другого - атомарен. Откат панели - то же самое с
# каталогом старого релиза.
ln -sfn "$RELEASE_DIR" "${WEB_DIR}/current.tmp"
mv -Tf "${WEB_DIR}/current.tmp" "${WEB_DIR}/current"

echo "==> Pruning old releases, keeping the newest ${KEEP_RELEASES} and the live one"
live="$(readlink -f "${WEB_DIR}/current")"
find "${WEB_DIR}/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -rn | cut -d' ' -f2- | tail -n "+$((KEEP_RELEASES + 1))" \
  | while IFS= read -r old; do
      [ "$(readlink -f "$old")" = "$live" ] && continue
      rm -rf "$old"
    done

rm -f "${INCOMING_DIR}/app.tar.gz" "${INCOMING_DIR}/web.tar.gz"
echo "==> Done: release ${RELEASE_SHA} is live"
