# 01. Архитектура

Статус: **Фаза 1: утверждено** (09.10.2026). Решения пользователя — источник
истины; производные решения и их обоснования — в `06-decisions.md`.

## Что за продукт

BrewQ — заказ напитков в **одной** кофейне. Два пользователя:

- **Клиент** — Android-приложение, без регистрации. Смотрит меню (coffee / tea /
  cake: название на английском, картинка, цена в AMD по размерам S/M/L),
  собирает **корзину, которая хранится на сервере**, оформляет заказ (оплата
  **только при получении**), видит статус текущего заказа и **код для
  получения** `A-042`, историю своих заказов. Может один раз указать имя —
  бариста увидит его рядом с кодом.
- **Бариста** — веб-панель. Входит по **одному общему паролю кофейни**, видит
  очередь, двигает статус (**только вперёд**), отменяет заказ (из `NEW` или
  `IN_PROGRESS`), видит тот же `code`, ставит/снимает позицию со стоп-листа.

Push-уведомлений нет. Android **поллит** статус раз в 5 секунд и при переходе в
`READY` показывает **локальное in-app уведомление** (не FCM). Панель тоже
поллит очередь раз в 5 секунд.

## Три репозитория

| Репозиторий | Что внутри |
|---|---|
| **BrewQ_infra** (этот) | backend (FastAPI), веб-панель баристы (React + Vite), медиа меню, CI/CD (GitHub Actions) с деплоем |
| BrewQ_image | Docker (compose + Dockerfile backend), Terraform (GCP), nginx **на хосте**, bootstrap VM, перенос секретов в GitHub |
| BrewQ_android | Kotlin + Jetpack Compose — клиент |

Контракт между репозиториями (пути, порты, `.env`, compose, секреты) —
**одинаковая** таблица в README всех трёх репозиториев.

## Стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, PyMySQL (`PyMySQL[rsa]`), Alembic, pytest, Pydantic v2, pydantic-settings, PyJWT, tzdata |
| Веб-панель | React + Vite + TypeScript (strict), react-i18next, TanStack Query |
| БД | MySQL 8.4 LTS (образ `mysql:8.4`), InnoDB, `utf8mb4` / `utf8mb4_0900_ai_ci` |
| Контейнеры | Docker Compose: `db` + `api` (nginx на хосте, панель — статика с диска) |
| Инфраструктура | Terraform (GCP) в `BrewQ_image`; `apply` — позже, когда будет аккаунт |
| CI/CD | GitHub Actions в этом репозитории |

`PyMySQL[rsa]` (то есть с `cryptography`) обязателен: MySQL 8 по умолчанию
использует `caching_sha2_password`, и без него первое подключение по не-TLS
соединению падает.

## Компоненты

```
┌──────────────┐  HTTP(S) /api/*  + X-Device-Id
│ Android      │──────────────────────────────┐
└──────────────┘                              ▼
                                   ┌─────────────────────┐   127.0.0.1:8081
┌──────────────┐  HTTP(S) /        │ nginx (хост, VM)    │──────────────▶ api (FastAPI, контейнер :8000)
│ Панель       │──────────────────▶│  /api/   → 8081     │                     │ PyMySQL
│ баристы      │  /api/barista/*   │  /media/ → диск     │                     ▼
└──────────────┘  Bearer <token>   │  /       → web/current (SPA)          db (MySQL, только docker-сеть)
                                   └─────────────────────┘
```

- Транспорт — REST, JSON, UTF-8. Базовый путь `/api`.
- Наружу (80/443) смотрит **только хостовый nginx** (конфиг — `BrewQ_image`).
  backend слушает loopback `127.0.0.1:8081`, MySQL не публикуется вовсе.
- Панель — статика (`npm run build`), лежит на диске в
  `/srv/brewq/web/current`; отдельного web-контейнера и порта 8082 **нет**
  (решение повторяет Miasin, см. `06-decisions.md`).
- Картинки меню — файлы `app/media/menu/*` этого репозитория, на сервере
  `/srv/brewq/app/media/`, раздаёт nginx по `/media/`.
- Панель и API — один origin, CORS не нужен. Android под CORS не подпадает.

## Идентичность клиента: `device_id`

- Android при первом запуске генерирует UUID v4, хранит в DataStore и шлёт
  заголовком **`X-Device-Id`** на каждом клиентском запросе.
- Backend держит его в `customers.device_id` (UNIQUE) и создаёт строку при
  первом запросе (upsert). В теле запроса `device_id` не бывает никогда.
- Ограничение (зафиксировано честно): идентификатор переживает выход из
  приложения и очистку кэша, **не переживает** «Очистить данные» и
  переустановку — для сервера это новый клиент, старая история недоступна.
- `device_id` — идентификатор, а не секрет: кто знает чужой UUID, тот видит
  чужие заказы. Компромисс принят: данные низкочувствительные (кофе, без
  платежей, имя необязательно). Подробно — `06-decisions.md`.
- Панель `X-Device-Id` не шлёт: у неё Bearer-токен баристы (`03-api.md`).

## Структура backend (слои как в Miasin, идиомы FastAPI)

```
app/backend/
  requirements.txt           — пины runtime-зависимостей (контракт с Dockerfile)
  requirements-dev.txt       — `-r requirements.txt` + pytest, httpx2, ruff (CI и разработка)
  pyproject.toml             — настройки ruff и pytest
  .dockerignore              — .venv, .env, tests и кэши не попадают в образ
  alembic.ini, alembic/      — миграции (линейная история)
  seed/menu.json             — меню как код (upsert по name)
  app/
    main.py                  — create_app(): роутеры, exception handlers, StaticFiles /media (только dev)
    boot.py                  — `python -m app.boot`: alembic upgrade + seed по флагам env
    seed.py                  — `python -m app.seed`
    api/
      deps.py                — get_db, get_clock, get_customer (X-Device-Id), require_barista
      routes/                — health, menu, me, cart, orders, barista_auth, barista_orders, barista_menu
    schemas/                 — Pydantic (запросы extra="forbid", ответы)
    services/                — customer, menu, cart, checkout, orders, order_views, order_transitions, barista_auth, barista_orders, errors
    domain/                  — чистая логика без БД: order_status (таблица переходов), sizes, categories, order_code, business_day
    repositories/            — SQLAlchemy-запросы, по файлу на таблицу
    models/                  — ORM-модели (по файлу на таблицу)
    core/                    — config (pydantic-settings), errors (конверт + handlers), logging, clock (Clock/SystemClock/FakeClock), security (пароль и JWT баристы)
    db/                      — base (Base, TABLE_OPTIONS), types (UtcDateTime, unsigned INT, str_enum/AsciiBinEnum), session (engine, sessionmaker), uow (транзакция сервиса)
  tests/
    unit/                    — domain/*, без БД
    integration/             — реальное приложение (TestClient) против живой MySQL
```

Правила слоёв:

1. Pydantic — только на HTTP-границе. Роутер: разбор запроса → вызов сервиса →
   схема ответа. Никакой бизнес-логики в роутере.
2. Сервис владеет транзакцией, инвариантами и статус-машиной.
3. Репозиторий не знает HTTP и не бросает `HTTPException`; доменные ошибки
   (`AppError(code, http_status, details)`) превращаются в конверт в одном
   exception handler.
4. Ограничивающее значение (`customer_id`) приходит в репозиторий из сервиса,
   а не от клиента: «чужой заказ» отсекается в одном месте SQL и выглядит как
   404.
5. Время — только через `Clock` (`core/clock.py`), чтобы тесты могли
   «перевести часы» через полночь по Еревану.

## Dependency Injection (FastAPI `Depends`)

- `get_db()` — сессия, закрывается в `finally`.
- `get_clock()` — `SystemClock` (UTC); в тестах подменяется.
- `get_customer()` — читает и валидирует `X-Device-Id`, находит или создаёт
  `customers` (upsert), отдаёт `Customer`. Используется всеми клиентскими
  роутерами.
- `require_barista()` — проверяет `Authorization: Bearer <JWT>`; используется
  всеми `/api/barista/*`, кроме `/api/barista/login`.

## Чего в системе нет намеренно

- Онлайн-оплаты и платёжных сущностей.
- Push (FCM) и фоновой работы на телефоне.
- Учётных записей барист и таблиц сессий: один пароль в `.env`, токен без
  состояния.
- Таблиц `categories`, `translations`, `devices`: категория — фиксированный
  набор значений, имена меню только на английском, устройство = `customers`.
- Редактирования меню через API: меню меняется в `seed/menu.json` и
  доезжает деплоем; бариста управляет только `is_available`.
- Бэкапов БД (риск записан в `BrewQ_image/memory/03-decisions.md`).

## Состояние реализации (B1–B3, 09.10.2026)

Сделано всё из `03-api.md`: каркас, `core/*` (config, errors, clock, logging, security),
`db/*` (включая `uow`), шесть ORM-моделей, миграция `0001`, `domain/*`, сид меню,
`app.seed`, `app.boot`, health, клиентский API (меню, `/me`, корзина, оформление,
заказы, отмена) и API баристы (вход, очередь, «Сегодня», смена статуса, меню/стоп-лист).
Сервисы — `customer`, `menu`, `cart`, `checkout`, `orders`, `order_views`,
`order_transitions`, `barista_auth`, `barista_orders`, `errors`; репозитории — по файлу на
таблицу. Решения реализации — `06-decisions.md`, разделы В и Г.

Детали, которые важны следующим задачам:

- **Сессия БД** кладётся в `app.state.session_factory` в `create_app()`; `get_db`
  достаёт её оттуда. Тесты строят приложение через `create_app(Settings(...))`.
- **Время**: `Clock.now()` возвращает aware-UTC; столбцы моделей — `UtcDateTime`
  (aware UTC в Python, `DATETIME(6)` в БД). Сырые SQL-параметры времени надо
  передавать naive UTC (в тестах — `helpers.db_dt`).
- **Ошибки**: все коды из `03-api.md` уже есть в `ErrorCode`; доменное исключение
  `DailyOrderLimitReached` бросает `domain/order_code.next_code`, сервис
  превращает его в `AppError(DAILY_ORDER_LIMIT_REACHED, 409)`.
- **Зависимости**: `app/main.py` создаёт `app = create_app()` на импорте, поэтому
  импорт `app.main` требует `DATABASE_URL` в окружении; юнит-тесты `app.main`
  не импортируют.
- **Код на английском**: комментарии, docstring и строки в `app/` и `tests/` без
  кириллицы (так проще проверка правила №5 в CI); документация — на русском.
- **Тесты**: `tests/unit` — без БД; `tests/integration` — против живой MySQL из
  `TEST_DATABASE_URL`/`DATABASE_URL`, имя базы обязано заканчиваться на `_test`
  (фикстура пересоздаёт схему). Фикстуры: `engine`, `conn`, `client`, `clean_tables`
  (автоочистка таблиц перед и после каждого теста); `tests/integration/helpers.py`
  — сырые вставки и `expect_db_error`.
