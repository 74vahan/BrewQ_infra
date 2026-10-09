# 07. План Фазы 2 (реализация)

Статус: **Фаза 1: утверждено** (09.10.2026). План для исполнителей.
Источники истины: `02-database.md`, `03-api.md`, контракт в README трёх
репозиториев. Любое отклонение от них — сначала вопрос пользователю (правило
№8), потом правка документа, потом код.

## Общие правила для всех агентов

- Перед началом — прочитать `memory/` своего репозитория и этот файл;
  `skills-lock.json` VibeCode (правило №12) — для Frontend/Android релевантны
  `frontend-design`, `web-design-guidelines`, `ui-ux-pro-max`.
- Версии библиотек — актуальные стабильные, уточнять через Context7; пины —
  в lock-файлах (`requirements.txt`, `package-lock.json`, `libs.versions.toml`).
- Один файл — одна ответственность (правило №7); секреты только в `.env`
  (правило №9); кириллица в коде — только в ru-локализации (правило №5,
  `ci/check-cyrillic.sh`).
- «Готово» = критерии ниже **выполнены и прогнаны** (правило №10). Что
  проверить нельзя — записать в INDEX своего репозитория как «не проверено».
- После задачи — обновить `memory/` и README своего репозитория.
- Ничего не пушить без явной просьбы пользователя.

## Граф зависимостей

```
Волна 0 (параллельно, сразу):   B1   D1   D2   F1   A1
Волна 1:                        B2 (←B1)   B3 (←B1)   D3 (←B1, D1, F1)
Волна 2:                        F2 (←B3, F1)   A2 (←B2, A1)
Волна 3:                        Q1 сквозная проверка (←всё выше)
Отложено до GCP-аккаунта:       P1 apply + секреты + первый деплой
```

F1/A1 пишут клиенты API по `03-api.md` с фейковыми данными, не дожидаясь
backend. D1 пишет compose по контракту и проверяет сборку, как только у B1
появились `requirements.txt` и `app.main`.

---

## B1. Backend: каркас, схема, сиды — Backend-агент

**Репо/папки:** `BrewQ_infra/app/backend/`, `BrewQ_infra/app/media/menu/`, `BrewQ_infra/.env.example`.

**Сделать:**
- Структура из `01-architecture.md`; `requirements.txt` с пинами
  (`fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `PyMySQL[rsa]`,
  `alembic`, `pydantic-settings`, `PyJWT`, `tzdata`; dev: `pytest`, `httpx`,
  `ruff`).
- `core/config.py` (env: `DATABASE_URL`, `BARISTA_PASSWORD`,
  `BARISTA_TOKEN_SECRET`, `BARISTA_TOKEN_TTL_HOURS`, `MIGRATE_ON_START`,
  `SEED_ON_START`, `SERVE_MEDIA`, `MEDIA_DIR`, `LOG_LEVEL`), `core/errors.py`
  (конверт, handlers для `AppError`, валидации → `VALIDATION_ERROR`,
  404/405/500), `core/clock.py`, `db/session.py`.
- ORM-модели шести таблиц, миграция `0001_initial_schema` **дословно** по
  `02-database.md` (включая `CHECK`, имена ограничений, функциональный
  `uq_orders_day_code` через `op.execute`, исключение его из autogenerate).
- `domain/`: `order_status.py`, `sizes.py`, `order_code.py`, `business_day.py`
  + исчерпывающие юнит-тесты.
- `seed/menu.json` (демо-меню: 4–6 coffee с S/M/L, 2–3 tea, 2–3 cake с одной
  ценой; цены — заглушки до ответа пользователя), `app/seed.py`, `app/boot.py`.
- `GET /api/health`, `GET /api/health/ready`.
- `.env.example` — все имена переменных, пустые значения.

**Готово, когда:**
- `ruff check` чистый; `pytest tests/unit` зелёный.
- Против MySQL 8.4 (`BrewQ_image/docker/docker-compose.dev.yml` или временный
  контейнер): `alembic upgrade head` → 6 таблиц + `alembic_version`;
  повторный запуск — no-op; `alembic check` без расхождений.
- Интеграционные тесты схемы: каждый `CHECK`/`UNIQUE` срабатывает;
  `uq_orders_day_code` — дубликат за сутки 1062, через ереванскую полночь —
  проходит; `EXPLAIN` запроса `MAX(code)` использует индекс.
- `python -m app.seed` дважды — одинаковый результат, `is_available` не
  перезаписан.
- `uvicorn app.main:app` отвечает на оба health-эндпоинта.

## B2. Backend: клиентский API — Backend-агент (←B1)

**Репо/папки:** `BrewQ_infra/app/backend/app/{api,schemas,services,repositories}`, `tests/integration/`.

**Сделать:** `get_customer` (X-Device-Id, upsert), `GET /api/menu`,
`GET/PUT /api/me`, корзина (5 эндпоинтов), `POST /api/orders` (транзакция
оформления из `02-database.md` с ретраем), `GET /api/orders/current`,
`GET /api/orders/{id}`, `GET /api/orders` (keyset), `POST /api/orders/{id}/cancel`.

**Готово, когда** (`pytest` против живой MySQL, всё зелёное):
- Каждый эндпоинт и каждый код ошибки из `03-api.md` клиентской части
  покрыт хотя бы одним тестом (формы ответов сверяются с контрактом).
- Гонки: 10 параллельных оформлений разных клиентов → коды подряд без
  дублей; двойное оформление одного клиента → 1 заказ + `ACTIVE_ORDER_EXISTS`;
  повторное добавление в корзину суммирует `qty`; лимит 20.
- Часы: заказ в 23:59:59 и 00:00:01 по Еревану → `A-00n` и `A-001`.
- `A-999` занят → `DAILY_ORDER_LIMIT_REACHED`, корзина цела.
- Чужой заказ/строка корзины → 404.

## B3. Backend: API баристы — Backend-агент (←B1, параллельно с B2)

**Сделать:** `POST /api/barista/login`, `require_barista`, очередь
(`scope=active|today`), смена статуса (compare-and-set + событие),
`GET/PATCH /api/barista/menu`.

**Готово, когда** (`pytest` против MySQL):
- Таблица переходов: все разрешённые проходят, все запрещённые → 409 с
  `allowed`; события пишутся в той же транзакции.
- Гонка «клиент cancel / бариста IN_PROGRESS» → ровно один успех, одно событие.
- Токен: неверный пароль → 401 `BARISTA_INVALID_PASSWORD`; просроченный,
  битый, подписанный другим ключом, со старым `pwv` → 401 `BARISTA_UNAUTHORIZED`.
- Стоп-лист: `PATCH` меняет только `is_available`; лишнее поле → 400.
- `scope=today` режет по ереванским суткам.

## F1. Веб-панель: каркас — Frontend-агент (сразу)

**Репо/папки:** `BrewQ_infra/app/web/`.

**Сделать:** Vite + React + TS strict, ESLint, структура из `04-web-barista.md`,
i18n en/ru/hy (все строки, включая коды ошибок и статусы), `api/client.ts`
(разбор конверта, не падает на не-JSON), типы по `03-api.md`, роутинг,
экран входа, Layout, локальный шрифт с армянскими глифами; dev-прокси
`/api`, `/media` → `127.0.0.1:8081`. Пока нет B3 — фейковый слой данных за
тем же интерфейсом.

**Готово, когда:** `npm ci && npm run lint && npm run build` зелёные;
`node ci/check-i18n.mjs` (пишет D3, до этого — локальная копия) — паритет
ключей; армянский рисуется глифами (проверено в браузере).

## F2. Веб-панель: экраны — Frontend-агент (←B3, F1)

**Сделать:** очередь (3 колонки, кнопки из `allowed_transitions`, отмена с
подтверждением, поллинг 5 с, сигнал нового заказа), «Сегодня», стоп-лист,
обработка 401/409/429/сети.

**Готово, когда:** `npm run build` зелёный; против локального backend
(compose dev) вручную пройден сценарий: вход → заказ, созданный через
`curl` клиентским API, появился ≤ 5 с со звуком → NEW → IN_PROGRESS → READY →
PICKED_UP → виден в «Сегодня»; отмена из NEW; позиция в стоп-листе видна
неактивной в `GET /api/menu`; переключение en/ru/hy без пропущенных строк.

## A1. Android: каркас — Android-агент (сразу)

**Репо/папки:** `BrewQ_android/` (весь проект).

**Сделать:** Gradle (тулчейн как в MiasinAndroid: AGP 9.4.1, Kotlin 2.4.20,
Gradle 9.6.0 с `distributionSha256Sum`, foojay → JDK 17, compileSdk 37,
minSdk 26 — сверить через Context7 на момент реализации), тема, три
`strings.xml`, `core/` (`ApiError`, `ErrorEnvelopeParser`, `ApiResult`,
`apiCall`), `DeviceIdProvider` + `DeviceIdInterceptor`, `AppContainer`,
Retrofit-интерфейсы по `03-api.md`, исключение DataStore `device` из бэкапа,
`network_security_config` (cleartext только `127.0.0.1`/`10.0.2.2` в debug).

**Готово, когда:** `./gradlew assembleDebug` и `./gradlew testDebugUnitTest`
зелёные; юнит-тесты: парсер конверта (включая HTML 502, пустое тело),
`DeviceIdProvider` (генерирует один раз, валидный UUID v4, переживает
пересоздание), интерцептор ставит заголовок.

## A2. Android: экраны — Android-агент (←B2, A1)

**Сделать:** экраны из `BrewQ_android/memory/02-screens.md`: меню, карточка
позиции, корзина, оформление с однократным предложением имени, статус заказа
с поллингом и in-app уведомлением на READY, история, настройки (имя, язык).

**Готово, когда:** `assembleDebug` + `testDebugUnitTest` зелёные (тесты
ViewModel: поллинг останавливается на терминальном статусе и в фоне,
уведомление READY показывается ровно один раз, `ACTIVE_ORDER_EXISTS` ведёт на
существующий заказ); на эмуляторе через `adb reverse tcp:8081 tcp:8081`
против локального backend пройден полный цикл вместе с панелью (F2) на трёх
языках.

## D1. DevOps: Docker — DevOps-агент (сразу; сборка — после B1)

**Репо/папки:** `BrewQ_image/docker/`, `BrewQ_image/.env.example`.

**Сделать:** `docker-compose.yml`, `docker-compose.dev.yml`,
`backend.Dockerfile` + `backend.Dockerfile.dockerignore` по
`BrewQ_image/memory/01-docker.md`.

**Готово, когда:** `docker compose config -q` (база и dev-оверлей);
`docker compose build api` против соседнего `../BrewQ_infra/app/backend`;
`up -d` → оба сервиса `healthy`; `curl 127.0.0.1:8081/api/health/ready` →
`ready`; MySQL доступна только на `127.0.0.1:53306` в dev и не опубликована в
базовом файле; контейнер `api` работает не от root.

## D2. DevOps: Terraform GCP — DevOps-агент (сразу, независимо)

**Репо/папки:** `BrewQ_image/terraform/`, `BrewQ_image/.github/workflows/image-ci.yml`.

**Сделать:** всё из `BrewQ_image/memory/02-terraform-gcp.md`: сеть, firewall,
VM, bootstrap (каталоги, `.env` один раз, заглушка панели en/ru/hy), nginx
шаблон (HTTP/HTTPS), TLS, outputs, `push-github-secrets.sh`,
`check-templates.sh`, workflow проверок.

**Готово, когда:** `terraform fmt -check -recursive`; `terraform init
-backend=false && terraform validate` (корень и `scripts/render`);
`check-templates.sh` — оба варианта nginx-конфига проходят `nginx -t`,
bootstrap — `bash -n`; `shellcheck` (в CI). `apply` **не выполняется**.

## D3. DevOps: CI/CD BrewQ_infra — DevOps-агент (←B1, D1, F1)

**Репо/папки:** `BrewQ_infra/.github/workflows/ci-cd.yml`, `BrewQ_infra/ci/`.

**Сделать:** задания и скрипты из `05-ci-cd.md`.

**Готово, когда:** локально прогнаны все шаги, выполнимые без GitHub:
`check-cyrillic.sh`, `check-i18n.mjs`, `bash -n` + `shellcheck` по `ci/*.sh`,
`build-bundle.sh` собирает архив ожидаемой структуры, `remote-deploy.sh`
прогнан против локального каталога-имитации `/srv/brewq` (с `.env` и без —
во втором случае падает с объяснением), YAML разобран парсером. Запуск на
раннере — после push (с разрешения пользователя).

## Q1. Сквозная проверка — оркестратор (←всё)

Локально: compose dev + панель (`npm run dev`) + эмулятор. Сценарии: полный
цикл заказа; отмена клиентом из NEW и запрет из IN_PROGRESS; стоп-лист во
время наполнения корзины; второй заказ при активном; смена языка везде;
`check-cyrillic.sh` по трём репозиториям; README и INDEX актуальны.

**Статус: выполнена 10.10.2026** — результаты и замечания в `INDEX.md` (раздел «Проверено в Q1»).

## P1. Отложено до GCP-аккаунта

`terraform apply` → `push-github-secrets.sh REPO=74vahan/BrewQ_infra` →
первый деплой (`workflow_dispatch`) → smoke-тест → выдать баристе пароль
(`terraform output -raw barista_password`) → домен и TLS → release-сборка
Android с боевым `API_BASE_URL`.
