#!/usr/bin/env bash
# Собирает два архива для деплоя (см. memory/05-ci-cd.md):
#
#   app.tar.gz  backend/ + docker/ + media/   -> /srv/brewq/app/ (заменяется целиком)
#   web.tar.gz  содержимое app/web/dist       -> /srv/brewq/web/releases/<sha>/
#
# Ничего не собирает сам (панель собирает npm в отдельном задании) и не лезет
# на сервер. Запуск руками:
#   IMAGE_DOCKER_DIR=../BrewQ_image/docker ci/build-bundle.sh
#
# Переменные:
#   OUT_DIR           куда класть архивы (по умолчанию <repo>/build/bundle; build/ в .gitignore)
#   IMAGE_DOCKER_DIR  docker/ из BrewQ_image на BREWQ_IMAGE_REF (по умолчанию <repo>/_image/docker)
#   BACKEND_DIR, MEDIA_DIR, WEB_DIST — исходники (по умолчанию app/backend, app/media, app/web/dist)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/build/bundle}"
IMAGE_DOCKER_DIR="${IMAGE_DOCKER_DIR:-${REPO_ROOT}/_image/docker}"
BACKEND_DIR="${BACKEND_DIR:-${REPO_ROOT}/app/backend}"
MEDIA_DIR="${MEDIA_DIR:-${REPO_ROOT}/app/media}"
WEB_DIST="${WEB_DIST:-${REPO_ROOT}/app/web/dist}"

fail() { echo "build-bundle: $*" >&2; exit 1; }

# Есть ли в списке (stdin-текст $1) строка $2 целиком. Намеренно НЕ `grep -q`:
# при -q grep выходит на первом совпадении, пишущий конец конвейера ловит SIGPIPE
# (exit 141), и под `set -o pipefail` проверка ложно падает на большом списке
# (список > 64 КБ не помещается в буфер пайпа). Здесь grep читает весь ввод.
list_has() { printf '%s\n' "$1" | grep -xF -- "$2" >/dev/null; }

[ -f "${BACKEND_DIR}/requirements.txt" ] || fail "no requirements.txt in ${BACKEND_DIR}"
[ -f "${IMAGE_DOCKER_DIR}/docker-compose.yml" ] || fail "no docker-compose.yml in ${IMAGE_DOCKER_DIR} (check out BrewQ_image and set IMAGE_DOCKER_DIR)"
[ -f "${IMAGE_DOCKER_DIR}/backend.Dockerfile" ] || fail "no backend.Dockerfile in ${IMAGE_DOCKER_DIR}"
[ -d "${MEDIA_DIR}/menu" ] || fail "no menu images in ${MEDIA_DIR}/menu"
[ -f "${WEB_DIST}/index.html" ] || fail "no built panel in ${WEB_DIST} (run npm run build in app/web first)"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "${STAGE}/backend" "${STAGE}/docker" "${STAGE}/media" "$OUT_DIR"

echo "==> Staging backend (without tests, caches, virtualenvs, local .env)"
tar -C "$BACKEND_DIR" \
    --exclude='.venv' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='.mypy_cache' \
    --exclude='*.egg-info' --exclude='.env' --exclude='.env.*' \
    -cf - . | tar -C "${STAGE}/backend" -xf -
rm -rf "${STAGE}/backend/tests"

echo "==> Staging docker/ from ${IMAGE_DOCKER_DIR}"
tar -C "$IMAGE_DOCKER_DIR" --exclude='.env' --exclude='.env.*' -cf - . | tar -C "${STAGE}/docker" -xf -

echo "==> Staging media/"
tar -C "$MEDIA_DIR" -cf - . | tar -C "${STAGE}/media" -xf -

echo "==> Packing app.tar.gz and web.tar.gz into ${OUT_DIR}"
# Владелец 0 и сортировка имён: архив не зависит от пользователя сборки и порядка файлов.
tar --sort=name --owner=0 --group=0 --numeric-owner \
    -czf "${OUT_DIR}/app.tar.gz" -C "$STAGE" backend docker media
tar --sort=name --owner=0 --group=0 --numeric-owner \
    -czf "${OUT_DIR}/web.tar.gz" -C "$WEB_DIST" .

echo "==> Verifying archive layout"
app_list="$(tar -tzf "${OUT_DIR}/app.tar.gz")"
for required in \
  backend/requirements.txt backend/alembic.ini backend/alembic/ backend/app/main.py \
  backend/seed/menu.json docker/docker-compose.yml docker/backend.Dockerfile media/menu/; do
  list_has "$app_list" "$required" || fail "app.tar.gz lacks ${required}"
done
if printf '%s\n' "$app_list" | grep -E '(^|/)(tests|__pycache__|\.venv|\.pytest_cache|\.ruff_cache)(/|$)|(^|/)\.env(\.|$)|\.pyc$' >/dev/null; then
  fail "app.tar.gz contains tests, caches or an .env file"
fi
web_list="$(tar -tzf "${OUT_DIR}/web.tar.gz")"
list_has "$web_list" './index.html' || fail "web.tar.gz lacks index.html"

ls -l "${OUT_DIR}/app.tar.gz" "${OUT_DIR}/web.tar.gz"
echo "OK: bundle is ready in ${OUT_DIR}"
