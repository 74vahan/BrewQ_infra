#!/usr/bin/env bash
# Проверки после деплоя по публичному адресу: каждая ловит поломку, которая
# иначе молчалива (API жив, а nginx отдаёт не то, и т. п.).
#
#   BASE_URL=https://example.org ci/smoke-test.sh
#
# Только curl, grep и sed: работает и на раннере, и на ноутбуке.
set -euo pipefail

BASE_URL="${BASE_URL:?BASE_URL is required}"
BASE_URL="${BASE_URL%/}"
# Фиксированный UUID v4: все прогоны создают одну служебную строку в customers,
# а не по новой на каждый деплой.
PROBE_DEVICE_ID="${PROBE_DEVICE_ID:-00000000-0000-4000-8000-000000000000}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "SMOKE FAILED: $*" >&2; exit 1; }

# get <имя> <путь> [заголовок...] -> код ответа в $code, тело в $TMP/<имя>.body,
# заголовки в $TMP/<имя>.head
get() {
  local name="$1" path="$2"
  shift 2
  local args=()
  local header
  for header in "$@"; do args+=(-H "$header"); done
  code="$(curl -sS --max-time 20 -o "${TMP}/${name}.body" -D "${TMP}/${name}.head" \
    -w '%{http_code}' "${args[@]}" "${BASE_URL}${path}")"
}

# Сервер мог только что перезапуститься: первый запрос — с повторами.
echo "==> GET /api/health (process is alive)"
curl -fsS --max-time 20 --retry 10 --retry-delay 3 --retry-all-errors \
  "${BASE_URL}/api/health" > "${TMP}/health.body" || fail "/api/health did not answer 200"
grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' "${TMP}/health.body" || fail "/api/health body: $(cat "${TMP}/health.body")"

echo "==> GET /api/health/ready (the database answers too)"
get ready /api/health/ready
[ "$code" = "200" ] || fail "/api/health/ready returned ${code}"
grep -Eq '"status"[[:space:]]*:[[:space:]]*"ready"' "${TMP}/ready.body" || fail "/api/health/ready body: $(cat "${TMP}/ready.body")"

echo "==> GET / (the panel is published)"
get index /
[ "$code" = "200" ] || fail "/ returned ${code}"
grep -qi '^content-type:[[:space:]]*text/html' "${TMP}/index.head" || fail "/ is not text/html"

echo "==> GET /today (SPA fallback in nginx)"
get today /today
[ "$code" = "200" ] || fail "/today returned ${code} (nginx try_files fallback broken?)"
grep -qi '^content-type:[[:space:]]*text/html' "${TMP}/today.head" || fail "/today is not text/html"

# Публичные статические файлы панели (R7): без входа, и это именно они, а не
# index.html из SPA-fallback (он тоже отвечает 200 на любой путь без файла).
echo "==> GET /privacy.html (public privacy policy, not the SPA fallback)"
get privacy /privacy.html
[ "$code" = "200" ] || fail "/privacy.html returned ${code}"
grep -qi '^content-type:[[:space:]]*text/html' "${TMP}/privacy.head" || fail "/privacy.html is not text/html"
grep -q '<h1>Privacy policy</h1>' "${TMP}/privacy.body" || fail "/privacy.html is not the privacy page (SPA fallback swallowed it?)"

echo "==> GET /robots.txt (private panel, crawlers kept out)"
get robots /robots.txt
[ "$code" = "200" ] || fail "/robots.txt returned ${code}"
grep -q '^Disallow: /' "${TMP}/robots.body" || fail "/robots.txt is not the robots file (SPA fallback swallowed it?)"

# Тот же приём, что для /today, но под /api/: должен дойти до backend и получить
# JSON-конверт ошибки, а не index.html. Ловит неверный порядок location в nginx.
echo "==> GET /api/no-such-route (reaches the API, not the SPA fallback)"
get nf /api/no-such-route
[ "$code" = "404" ] || fail "/api/no-such-route returned ${code}, expected 404"
grep -q 'NOT_FOUND' "${TMP}/nf.body" || fail "/api/no-such-route is not the JSON error envelope (is /api/ served by the SPA?)"

echo "==> GET /api/menu (the seed was applied)"
get menu /api/menu "X-Device-Id: ${PROBE_DEVICE_ID}"
[ "$code" = "200" ] || fail "/api/menu returned ${code}"
grep -Eq '"items"[[:space:]]*:[[:space:]]*\[[[:space:]]*\{' "${TMP}/menu.body" || fail "/api/menu has no items"

image_path="$(grep -Eo '"image_url"[[:space:]]*:[[:space:]]*"/media/menu/[^"]+"' "${TMP}/menu.body" \
  | head -n 1 | sed -E 's/.*"(\/media\/menu\/[^"]+)"$/\1/' || true)"
[ -n "$image_path" ] || fail "/api/menu has no image_url under /media/menu/"

echo "==> GET ${image_path} (menu images are served)"
get media "$image_path"
[ "$code" = "200" ] || fail "${image_path} returned ${code}"
grep -qi '^content-type:[[:space:]]*image/' "${TMP}/media.head" || fail "${image_path} is not image/*"

echo "OK: smoke test passed for ${BASE_URL}"
