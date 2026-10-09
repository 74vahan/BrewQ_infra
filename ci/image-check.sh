#!/usr/bin/env bash
# Собирает и запускает ТОТ ЖЕ образ api, что поедет на сервер: compose-файлы и
# Dockerfile берутся из BrewQ_image (в CI он клонируется в _image/), код — из
# этого репозитория.
#
#   IMAGE_DOCKER_DIR=../BrewQ_image/docker ci/image-check.sh
#
# Шаги: compose config -q (база и dev-оверлей) -> build api -> up -d ->
# ожидание /api/health/ready -> down -v. Временный проект brewq-ci и случайный
# .env (write-ci-env.sh): ничего «боевого» не затрагивается.
#
# Переменные:
#   IMAGE_DOCKER_DIR  каталог docker/ из BrewQ_image (по умолчанию <repo>/_image/docker)
#   BACKEND_CONTEXT   каталог backend (по умолчанию <repo>/app/backend)
#   BACKEND_PORT      порт на 127.0.0.1 (по умолчанию 8081)
#   READY_TIMEOUT     сколько секунд ждать готовности (по умолчанию 120)
#   COMPOSE_PROJECT   имя проекта (по умолчанию brewq-ci)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_DOCKER_DIR="${IMAGE_DOCKER_DIR:-${REPO_ROOT}/_image/docker}"
BACKEND_CONTEXT="${BACKEND_CONTEXT:-${REPO_ROOT}/app/backend}"
BACKEND_PORT="${BACKEND_PORT:-8081}"
READY_TIMEOUT="${READY_TIMEOUT:-120}"
PROJECT="${COMPOSE_PROJECT:-brewq-ci}"

[ -f "${IMAGE_DOCKER_DIR}/docker-compose.yml" ] || {
  echo "No docker-compose.yml in ${IMAGE_DOCKER_DIR} (set IMAGE_DOCKER_DIR)" >&2
  exit 1
}
[ -f "${BACKEND_CONTEXT}/requirements.txt" ] || {
  echo "No requirements.txt in ${BACKEND_CONTEXT} (set BACKEND_CONTEXT)" >&2
  exit 1
}

export BACKEND_CONTEXT BACKEND_PORT
ENV_FILE="$(mktemp)"
"${REPO_ROOT}/ci/write-ci-env.sh" "$ENV_FILE" >/dev/null

compose() {
  docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "${IMAGE_DOCKER_DIR}/docker-compose.yml" "$@"
}

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "==> FAILED, container state and recent logs:" >&2
    compose ps -a >&2 || true
    compose logs --tail 80 >&2 || true
  fi
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
  exit "$status"
}
trap cleanup EXIT

echo "==> docker compose config (base)"
compose config -q
echo "==> docker compose config (base + dev overlay)"
docker compose -p "$PROJECT" --env-file "$ENV_FILE" \
  -f "${IMAGE_DOCKER_DIR}/docker-compose.yml" -f "${IMAGE_DOCKER_DIR}/docker-compose.dev.yml" config -q

echo "==> docker compose build api (BACKEND_CONTEXT=${BACKEND_CONTEXT})"
compose build api

echo "==> docker compose up -d"
compose up -d

echo "==> Waiting for http://127.0.0.1:${BACKEND_PORT}/api/health/ready (up to ${READY_TIMEOUT}s)"
deadline=$((SECONDS + READY_TIMEOUT))
until curl -fsS --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/api/health/ready" >/dev/null 2>&1; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "The API did not become ready within ${READY_TIMEOUT}s" >&2
    exit 1
  fi
  sleep 3
done
echo "==> Ready: $(curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/health/ready")"
echo "OK: the image builds and the stack comes up healthy"
