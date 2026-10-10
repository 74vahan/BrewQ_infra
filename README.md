# BrewQ_infra

Backend (FastAPI), веб-панель баристы (React + Vite) и CI/CD (GitHub Actions)
проекта **BrewQ** — заказ напитков в одной кофейне. Android-клиент —
[`BrewQ_android`](https://github.com/74vahan/BrewQ_android). Docker, Terraform
(GCP) и nginx на хосте — [`BrewQ_image`](https://github.com/74vahan/BrewQ_image).

Статус: Фаза 1 (планирование) завершена. Фаза 2 (реализация) идёт по
`memory/07-implementation-plan.md`: backend готов целиком (B1 каркас, схема,
миграция, сид, health; B2 клиентский API; B3 API баристы), веб-панель готова
(F1 каркас, F2 экраны), CI/CD написан (D3; раннер GitHub и сервер не
проверялись). Сквозная проверка Q1 (Android-эмулятор + панель + backend в
Docker) пройдена 10.10.2026 — `memory/INDEX.md`. Остаётся P1: деплой после
появления GCP-аккаунта.

## Что здесь

| Путь | Что |
|---|---|
| `app/backend/` | FastAPI + SQLAlchemy 2 + PyMySQL + Alembic + pytest; слои routes → services → repositories |
| `app/web/` | React + Vite + TypeScript: очередь заказов, смена статуса, стоп-лист; i18n en/ru/hy; шрифт Sora из npm; публичная политика конфиденциальности `/privacy.html` (+ `.ru`, `.hy`) со значениями `TODO(user)` — заполнить владельца и контакт перед релизом |
| `app/media/menu/` | картинки меню (раздаёт nginx по `/media/`) |
| `ci/` | скрипты проверок, сборки архива, деплоя и smoke-теста |
| `.github/workflows/ci-cd.yml` | тесты против MySQL, сборка панели, сборка образа, деплой на VM |
| `memory/` | архитектура, схема БД, контракт API, решения, план |

## Бизнес-правила (подробно — `memory/`)

- Без регистрации: клиент = `device_id` (UUID v4) в заголовке `X-Device-Id`.
- Корзина хранится на сервере; заказ создаётся из неё одной транзакцией.
- Код получения `A-001`…`A-999`, счётчик сбрасывается каждые сутки по Еревану.
- Статусы `NEW → IN_PROGRESS → READY → PICKED_UP` (+ `CANCELLED`), только вперёд;
  один активный заказ на клиента.
- Бариста входит по одному общему паролю кофейни из `.env`.
- Оплата при получении; push-уведомлений нет — поллинг каждые 5 секунд.

## Контракт между репозиториями (Фаза 1: утверждено, 09.10.2026)

> Эта таблица **дословно одинакова** в README `BrewQ_infra`, `BrewQ_image` и
> `BrewQ_android`. Меняется только во всех трёх сразу.

| Что | Значение | Владелец |
|---|---|---|
| Корень на сервере | `/srv/brewq` (Terraform `app_root`, CI `APP_ROOT`) | BrewQ_image (создаёт bootstrap) |
| Пользователь SSH/деплоя, владелец `/srv/brewq` | `brewq` (Terraform `ssh_user` = секрет `SERVER_USER`); деплою sudo не нужен | BrewQ_image |
| Файл окружения | `/srv/brewq/.env`, режим 600, пишется **один раз** bootstrap'ом | BrewQ_image; деплой только читает и без файла падает |
| Ключи `.env` | `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `BARISTA_PASSWORD`, `BARISTA_TOKEN_SECRET`, `BARISTA_TOKEN_TTL_HOURS`, `BACKEND_PORT`, `PUBLIC_BASE_URL`, `LOG_LEVEL` | BrewQ_image пишет, compose читает |
| Приложение | `/srv/brewq/app/` = `backend/` + `docker/` + `media/`, заменяется целиком каждым деплоем | BrewQ_infra (CI); `docker/` — копия `BrewQ_image/docker/` на `BREWQ_IMAGE_REF` |
| Веб-панель | `/srv/brewq/web/releases/<sha>/`, живой корень — симлинк `/srv/brewq/web/current` | BrewQ_infra (CI); заглушку `releases/bootstrap` ставит BrewQ_image |
| Картинки меню | файлы `/srv/brewq/app/media/menu/*`, URL `/media/menu/<file>`, в БД — относительный путь | файлы — BrewQ_infra, раздача nginx — BrewQ_image |
| Compose | project `brewq`, файл `docker/docker-compose.yml`, сервисы `db` (`mysql:8.4`) и `api` (образ `brewq-api`), том `brewq-db-data`; контекст сборки `api` — `${BACKEND_CONTEXT}` | BrewQ_image |
| Dockerfile ↔ backend | в контексте: `requirements.txt`, пакет `app/`, `alembic.ini`, `alembic/`, `seed/`; старт `python -m app.boot && uvicorn app.main:app --port 8000` | BrewQ_image ↔ BrewQ_infra |
| Порт backend | `127.0.0.1:8081` → `api:8000` (Terraform `backend_port`, env `BACKEND_PORT`) | BrewQ_image публикует, nginx проксирует |
| MySQL | `db:3306` только в docker-сети; наружу не публикуется; firewall deny 3306; dev-оверлей — `127.0.0.1:53306` | BrewQ_image |
| Открытые порты VM | 80, 443 (nginx на хосте), 22 (SSH по ключу) | BrewQ_image |
| nginx | `/etc/nginx/sites-available/brewq`; `/api/` → `127.0.0.1:8081`; `/media/` → диск; `/` → `web/current` (SPA-fallback) | BrewQ_image |
| Health | `GET /api/health` (жив), `GET /api/health/ready` (БД) | BrewQ_infra |
| GitHub `74vahan/BrewQ_infra` | secrets `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS`; variables `APP_ROOT`, `PUBLIC_BASE_URL` — кладёт `BrewQ_image/terraform/scripts/push-github-secrets.sh`; variable `BREWQ_IMAGE_REF` (по умолчанию `main`) — вручную | BrewQ_image → BrewQ_infra |
| API для Android | `<PUBLIC_BASE_URL>/api/`; debug — `http://127.0.0.1:8081/api/` через `adb reverse tcp:8081 tcp:8081` | BrewQ_android |
| Контракт API | `BrewQ_infra/memory/03-api.md`, ошибки `{"error":{"code","message","details"}}`, клиент — заголовок `X-Device-Id` (UUID v4) | BrewQ_infra |
| Локальная раскладка | репозитории — соседи: `DrewQ/BrewQ_infra`, `DrewQ/BrewQ_image`, `DrewQ/BrewQ_android`; `BACKEND_CONTEXT` по умолчанию `../../BrewQ_infra/app/backend` | все |

## Локальный запуск

### Backend без Docker (разработка и тесты)

Нужны Python 3.12 и MySQL 8.4 (подойдёт временный контейнер):

```bash
# MySQL для разработки/тестов (пароли — свои, локальные)
docker run -d --name brewq-mysql -e MYSQL_ROOT_PASSWORD=<root-pw> -e MYSQL_DATABASE=brewq_test \
  -e MYSQL_USER=brewq -e MYSQL_PASSWORD=<pw> -p 127.0.0.1:53307:3306 mysql:8.4

cd app/backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# app/backend/.env (в git не попадает; шаблон — ../../.env.example)
#   DATABASE_URL=mysql+pymysql://brewq:<pw>@127.0.0.1:53307/brewq_test?charset=utf8mb4

ruff check .                       # линтер
pytest tests/unit                  # юнит-тесты, БД не нужна
alembic upgrade head               # схема: 6 таблиц + alembic_version
python -m app.seed                 # меню из seed/menu.json (повторный запуск безопасен)
SERVE_MEDIA=true uvicorn app.main:app --port 8081   # /api/health, /api/health/ready, /media/*
pytest                             # всё, включая интеграционные тесты против MySQL
```

Ручной прогон полного цикла (порт 8081 на машине может быть занят — берите любой,
ниже 18081; `BARISTA_PASSWORD`/`BARISTA_TOKEN_SECRET` (≥ 32 символов) — в `app/backend/.env`):

```bash
B=http://127.0.0.1:18081/api; D="X-Device-Id: 3f2504e0-4f89-41d3-9a0c-0305e82c3301"; J="Content-Type: application/json"
curl -s -H "$D" $B/menu                                                   # меню со стоп-листом
curl -s -X POST -H "$D" -H "$J" -d '{"menu_item_id":4,"size":"M","qty":2}' $B/cart/items
curl -s -X POST -H "$D" $B/orders                                          # 201, code A-001
TOKEN=$(curl -s -X POST -H "$J" -d "{\"password\":\"$BARISTA_PASSWORD\"}" $B/barista/login | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -H "Authorization: Bearer $TOKEN" $B/barista/orders                # очередь
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "$J" -d '{"to":"IN_PROGRESS"}' $B/barista/orders/1/status
curl -s -H "$D" $B/orders/current                                          # клиент видит статус
```

Интеграционные тесты не требуют `BARISTA_*` в окружении: пароль и секрет они
генерируют сами на каждый прогон. Полный набор (`pytest`) идёт около полутора минут.

Интеграционные тесты **стирают и пересоздают схему** базы из `TEST_DATABASE_URL`
(или `DATABASE_URL`), поэтому имя базы обязано заканчиваться на `_test`, иначе
тесты откажутся запускаться. Для базы разработки `brewq` заведите рядом базу
`brewq_test` и укажите на неё `TEST_DATABASE_URL`.

Контейнерный старт (`python -m app.boot`) сам выполняет `alembic upgrade head`
и сид при `MIGRATE_ON_START=true` / `SEED_ON_START=true`.

### Весь стек в Docker и панель

```bash
# 1. MySQL + api в Docker (файлы — в соседнем BrewQ_image)
cd ../BrewQ_image && cp .env.example .env   # заполнить пароли
docker compose -p brewq-dev --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build

# 2. Панель (Vite проксирует /api и /media на 127.0.0.1:8081)
cd ../BrewQ_infra/app/web && npm ci && VITE_USE_FAKE_API=false npm run dev
```

Если порт 8081 на машине занят (так у нас: чужой контейнер), поднимайте стек с
`BACKEND_PORT=18090 docker compose ...` (перед `docker compose`), панель — с
`VITE_API_TARGET=http://127.0.0.1:18090`, а Android-эмулятор — с
`adb reverse tcp:8081 tcp:18090` (debug-сборка ходит на `127.0.0.1:8081`).
Локальный проект compose называется `brewq-dev`, чтобы не путать с серверным
`brewq`. После смены `BARISTA_PASSWORD` в `.env` пересоздайте `api`:
`... up -d --force-recreate api`.

### Панель отдельно, без backend

Панель (задачи F1–F2: очередь из трёх колонок, «Сегодня», стоп-лист, звук
нового заказа) запускается сама по себе: `npm run dev` по умолчанию берёт
фейковый слой данных в памяти (демо-заказы и меню, жёлтая полоса «Демо-данные»
с кнопкой «Добавить демо-заказ»), входит любой непустой пароль. В консоли
браузера доступен `window.brewqFake` (`addOrder()`, `advanceBehindUi()`,
`setOffline()`, `failNext()`, `expireSession()`) — им проверяют гонки, обрыв
связи, 429 и 401 без backend. Звук после перезагрузки страницы включается
первым касанием (политика autoplay браузера). Нужен Node >= 20.19.

```bash
cd app/web
npm ci
npm run dev                                          # http://localhost:5173, фейковые данные
VITE_USE_FAKE_API=false npm run dev                  # реальный backend через прокси на 127.0.0.1:8081
VITE_FAKE_API_PASSWORD=<любая-строка> npm run dev    # фейковый вход только с этим паролем

npm run lint && npm test && npm run check:i18n && npm run build   # проверки, как в CI
```

Переменные — в `app/web/.env.example` (пустые, секретов нет; пароль баристы в
код не зашит). Production-сборка всегда ходит в реальный API. Подробно —
`memory/04-web-barista.md`.

## CI/CD и деплой

Workflow — `.github/workflows/ci-cd.yml` (триггеры: push в `main`, PR, ручной
запуск); вся логика — в скриптах `ci/`, их можно запускать руками.

| Задание | Что делает |
|---|---|
| `quality` | `ruff check` / `ruff format --check`, `ci/check-cyrillic.sh`, `ci/check-i18n.mjs`, `bash -n` + `shellcheck`, `actionlint` |
| `backend-tests` | `mysql:8.4`, `alembic upgrade head`, `pytest` (unit + integration) |
| `build-web` | `npm ci`, `lint`, `test`, `build` панели |
| `image` | клонирует `BrewQ_image` (`vars.BREWQ_IMAGE_REF`, по умолчанию `main`), собирает образ `api` и поднимает стек до `/api/health/ready` |
| `deploy` | только push в `main` / ручной запуск: архивы `app.tar.gz` + `web.tar.gz` -> SSH на VM -> `docker compose up -d --build` -> переключение `web/current` -> smoke-тест |

Пока секретов сервера нет (GCP-аккаунта ещё нет), деплой пропускается с
`::notice` и остаётся зелёным; архивы при этом всё равно собираются.

Секреты `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS` и
переменные `APP_ROOT`, `PUBLIC_BASE_URL` кладёт
`BrewQ_image/terraform/scripts/push-github-secrets.sh`; `BREWQ_IMAGE_REF` — вручную.
Деплой **не создаёт** `/srv/brewq/.env` (его пишет bootstrap из `BrewQ_image`) и
без него падает с объяснением.

Проверки локально (из корня репозитория):

```bash
bash ci/check-cyrillic.sh && node ci/check-i18n.mjs && bash ci/check-shell.sh
bash ci/lint-backend.sh                                          # нужен ruff
IMAGE_DOCKER_DIR=../BrewQ_image/docker bash ci/image-check.sh    # Docker; BACKEND_PORT=... если 8081 занят
IMAGE_DOCKER_DIR=../BrewQ_image/docker bash ci/build-bundle.sh   # архивы в build/bundle/
BASE_URL=https://<домен> bash ci/smoke-test.sh                   # после деплоя
```

Откат: панель — переключить симлинк `web/current` на каталог старого релиза;
backend — `workflow_dispatch` на старом теге. Подробно — `memory/05-ci-cd.md`.
