# 02. База данных (MySQL 8.4)

Статус: **Фаза 1: утверждено** (09.10.2026). Имена таблиц и столбцов заданы
пользователем и **не меняются** без его явного согласия. Других таблиц нет,
кроме технической `alembic_version`.

## Таблицы и связи

```
customers 1──∞ cart_items ∞──1 menu_items
    │                              │
    1                              1
    ∞                              ∞
  orders 1──∞ order_items ─────────┘
    │
    1──∞ order_events
```

## Общие соглашения

- InnoDB, `utf8mb4`, `utf8mb4_0900_ai_ci` (имена клиентов могут быть на
  армянском/русском).
- **Все времена — UTC в `DATETIME(6)`** (не `TIMESTAMP`): значение пишет
  приложение из `Clock`, MySQL ничего не конвертирует. `TIMESTAMP` запрещён:
  выражения от него зависят от `time_zone` сессии и не допускаются в
  функциональном индексе (см. `orders`). В API время уходит как ISO 8601 с `Z`.
- Деньги — целые `INT UNSIGNED` в AMD (у драма нет копеек).
- Перечисления — `VARCHAR` + именованный `CHECK` (MySQL 8.0.16+ их соблюдает),
  в SQLAlchemy — `Enum(..., native_enum=False, create_constraint=True)`.
  Почему не `ENUM` — `06-decisions.md`.
- Значения: `category ∈ {coffee, tea, cake}`, `size ∈ {S, M, L}`,
  `status ∈ {NEW, IN_PROGRESS, READY, PICKED_UP, CANCELLED}` — ровно эти
  строки, в этом регистре, в БД и в API. Чтобы `CHECK` был **регистрозависимым**,
  столбцы `category`, `size`, `status`, `from_status`, `to_status` (и `orders.code`)
  объявлены `CHARACTER SET ascii COLLATE ascii_bin`: `status = 'new'` в сыром SQL
  даёт `3819`, а не проходит молча (`db/types.py`: `AsciiBinEnum`).
- **Физических удалений нет**, кроме строк корзины. Все FK — `ON DELETE
  RESTRICT`, кроме `cart_items.customer_id` (`CASCADE`, безвредно).
- Имена ограничений и индексов — явные (`uq_`, `ix_`, `fk_`, `ck_`), чтобы
  Alembic и сообщения об ошибках были предсказуемы.

## `menu_items`

| Столбец | Тип | Заметки |
|---|---|---|
| `id` | `INT UNSIGNED` PK AI | |
| `name` | `VARCHAR(100) NOT NULL` | только английский; `uq_menu_items_name` (регистронезависимо) |
| `category` | `VARCHAR(16) ascii_bin NOT NULL` | `ck_menu_items_category`: `coffee`/`tea`/`cake` |
| `price_s` | `INT UNSIGNED NULL` | NULL = размера S нет |
| `price_m` | `INT UNSIGNED NOT NULL` | есть всегда; у позиции с одним размером цена здесь |
| `price_l` | `INT UNSIGNED NULL` | NULL = размера L нет |
| `is_available` | `BOOLEAN NOT NULL DEFAULT TRUE` | **стоп-лист**; FALSE = временно нет |
| `image_url` | `VARCHAR(255) NULL` | относительный путь `/media/menu/<file>` или NULL |

`ck_menu_items_prices`: `price_m > 0 AND (price_s IS NULL OR price_s > 0) AND
(price_l IS NULL OR price_l > 0)`.

**Правило размера:** размер допустим, только если соответствующий `price_*`
не NULL (`domain/sizes.py`: `price_for(item, size) -> int | None`). Нарушение →
`400 SIZE_NOT_OFFERED`.

**Позиции не удаляются и не переименовываются по смыслу:** в `order_items`
нет снапшота имени, история показывает текущее `menu_items.name`. Убрать
позицию из продажи = `is_available = FALSE`. Исправление опечатки в имени
допустимо.

## `customers`

| Столбец | Тип | Заметки |
|---|---|---|
| `id` | `BIGINT UNSIGNED` PK AI | |
| `device_id` | `CHAR(36) CHARACTER SET ascii NOT NULL` | `uq_customers_device_id`; UUID v4 в нижнем регистре |
| `name` | `VARCHAR(40) NULL DEFAULT NULL` | необязательно; бариста видит рядом с кодом |
| `created_at` | `DATETIME(6) NOT NULL` | первый запрос |

Upsert (`get_customer`): `SELECT` по `device_id`; если нет —
`INSERT ... ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)` (безопасно при
гонке двух первых запросов). Поллинг раз в 5 секунд — это один индексный
`SELECT`, без записи.

## `cart_items` — корзина на сервере

| Столбец | Тип | Заметки |
|---|---|---|
| `id` | `BIGINT UNSIGNED` PK AI | |
| `customer_id` | `BIGINT UNSIGNED NOT NULL` | `fk_cart_items_customer` → customers, `ON DELETE CASCADE` |
| `menu_item_id` | `INT UNSIGNED NOT NULL` | `fk_cart_items_menu_item` → menu_items, `RESTRICT` |
| `size` | `VARCHAR(1) ascii_bin NOT NULL` | `ck_cart_items_size` |
| `qty` | `SMALLINT UNSIGNED NOT NULL` | `ck_cart_items_qty`: `qty BETWEEN 1 AND 20` |
| `updated_at` | `DATETIME(6) NOT NULL` | |

`uq_cart_items_line (customer_id, menu_item_id, size)`. Повторное добавление
того же товара/размера: `INSERT ... ON DUPLICATE KEY UPDATE qty = qty + :qty`
с проверкой лимита 20 (превышение → `409 CART_QTY_LIMIT_EXCEEDED`, строка не
меняется).

Позиция, ушедшая в стоп-лист **после** добавления, остаётся в корзине и
помечается в ответе `problem: "unavailable"`; оформить такую корзину нельзя.

## `orders`

| Столбец | Тип | Заметки |
|---|---|---|
| `id` | `BIGINT UNSIGNED` PK AI | технический id (в URL) |
| `code` | `CHAR(5) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` | `A-001`…`A-999`, номер для получения; `ck_orders_code`: `code REGEXP '^A-[0-9]{3}$' AND code <> 'A-000'` (ровно три цифры, регистр важен) |
| `customer_id` | `BIGINT UNSIGNED NOT NULL` | `fk_orders_customer`, `RESTRICT` |
| `status` | `VARCHAR(16) ascii_bin NOT NULL DEFAULT 'NEW'` | `ck_orders_status` |
| `total_amd` | `INT UNSIGNED NOT NULL` | `Σ unit_price_amd × qty`, считает сервер |
| `created_at` | `DATETIME(6) NOT NULL` | UTC |
| `updated_at` | `DATETIME(6) NOT NULL` | UTC, = время последнего события |

Индексы:

| Имя | Определение | Зачем |
|---|---|---|
| `uq_orders_day_code` | `UNIQUE ((DATE(created_at + INTERVAL 4 HOUR)), code)` | уникальность кода в пределах ереванских суток; та же сортировка даёт `MAX(code)` за день; тем же выражением отбирается список «Сегодня» баристы (`EXPLAIN` — `key=uq_orders_day_code`) |
| `ix_orders_customer_created` | `(customer_id, created_at)` | история клиента, проверка активного заказа, индекс под FK |
| `ix_orders_status_created` | `(status, created_at)` | очередь баристы |

### Генерация `code` (решение, подробно — `06-decisions.md`)

- Ереванские сутки: `business_day(now_utc) = (now_utc + 4h).date()`
  (`domain/business_day.py`). Asia/Yerevan — постоянный UTC+4 без перехода на
  летнее время с 2012 года. То же выражение стоит в функциональном индексе.
  Юнит-тест сверяет константу с `zoneinfo.ZoneInfo("Asia/Yerevan")` на
  ближайшие годы и упадёт, если tzdata когда-нибудь скажет другое; тогда
  меняются вместе константа и индекс (миграцией).
- Внутри транзакции оформления:
  `SELECT MAX(code) FROM orders WHERE DATE(created_at + INTERVAL 4 HOUR) = :day`
  (выражение **дословно** как в индексе, чтобы оптимизатор взял индекс; коды
  zero-padded, поэтому строковый MAX = числовой) → `n + 1` → `A-%03d`.
- `created_at` нового заказа = тот же `now`, по которому считался `day`
  (одно значение из `Clock`), поэтому код и сутки не могут разойтись на
  полуночи.
- Гонка двух оформлений разных клиентов: обе читают одинаковый MAX, вторая
  вставка ждёт на уникальном ключе и получает 1062 → вся транзакция
  оформления откатывается и повторяется (до **15** попыток с джиттером 0–30 мс;
  так же на deadlock 1213). Уникальность гарантирует индекс, а не код
  приложения. Почему не 3: при N одновременных оформлениях за раунд
  выигрывает один, последнему нужно до N попыток (замер: 10 параллельных
  оформлений доходят до 9-й попытки).
- Коды отменённых заказов не переиспользуются.
- Следующий был бы `A-1000` → `409 DAILY_ORDER_LIMIT_REACHED`, заказ не
  создаётся, корзина цела.

### Один активный заказ

Активные статусы — `NEW`, `IN_PROGRESS`, `READY`. Проверка в транзакции
оформления **после** `SELECT ... FROM customers WHERE id = :id FOR UPDATE`:
блокировка строки клиента сериализует двойное нажатие «Оформить», и второй
запрос честно получает `409 ACTIVE_ORDER_EXISTS`.

## `order_items`

| Столбец | Тип | Заметки |
|---|---|---|
| `id` | `BIGINT UNSIGNED` PK AI | |
| `order_id` | `BIGINT UNSIGNED NOT NULL` | `fk_order_items_order`, `RESTRICT` |
| `menu_item_id` | `INT UNSIGNED NOT NULL` | `fk_order_items_menu_item`, `RESTRICT` |
| `size` | `VARCHAR(1) ascii_bin NOT NULL` | `ck_order_items_size` |
| `qty` | `SMALLINT UNSIGNED NOT NULL` | `ck_order_items_qty`: 1..20 |
| `unit_price_amd` | `INT UNSIGNED NOT NULL` | **цена на момент заказа** (`ck_order_items_price`: > 0) |

`uq_order_items_line (order_id, menu_item_id, size)` — строки переносятся из
корзины, где та же уникальность.

## `order_events` — аудит

| Столбец | Тип | Заметки |
|---|---|---|
| `id` | `BIGINT UNSIGNED` PK AI | |
| `order_id` | `BIGINT UNSIGNED NOT NULL` | `fk_order_events_order`, `RESTRICT` |
| `from_status` | `VARCHAR(16) ascii_bin NULL` | NULL у события создания |
| `to_status` | `VARCHAR(16) ascii_bin NOT NULL` | |
| `created_at` | `DATETIME(6) NOT NULL` | UTC |

`ix_order_events_order (order_id, created_at)`. Оба статус-столбца с тем же
`CHECK`, что и `orders.status` (для `from_status` — с допуском NULL).
Каждая смена статуса пишет событие **в той же транзакции**.

Ограничение схемы (принято): кто сменил статус (клиент или бариста), не
хранится — столбца нет.

## Статус-машина

```
NEW ──▶ IN_PROGRESS ──▶ READY ──▶ PICKED_UP
 │           │
 └────┬──────┘
      ▼
  CANCELLED
```

| Из | В | Кто |
|---|---|---|
| — | `NEW` | система при оформлении |
| `NEW` | `IN_PROGRESS` | бариста |
| `IN_PROGRESS` | `READY` | бариста |
| `READY` | `PICKED_UP` | бариста |
| `NEW` | `CANCELLED` | клиент или бариста |
| `IN_PROGRESS` | `CANCELLED` | бариста |

Только следующий шаг: пропуск (`NEW → READY`) и любое движение назад
запрещены. `PICKED_UP` и `CANCELLED` терминальны. Таблица переходов — чистая
функция в `domain/order_status.py`, покрыта исчерпывающим юнит-тестом
(все 5×5 пар × 2 роли).

Применение перехода (`services/order_transitions.apply_transition`, единственное
место смены статуса; им пользуются и клиент, и бариста) атомарно и безопасно к гонкам:
`UPDATE orders SET status = :to, updated_at = :now WHERE id = :id AND status = :from`
— если затронуто 0 строк, статус успел смениться (например, клиент отменил,
пока бариста нажимал «Начать») → перечитать → `409`.

## Оформление заказа (одна транзакция)

1. `now = clock.now()`, `day = business_day(now)`.
2. `SELECT customers ... FOR UPDATE`.
3. Есть активный заказ → `409 ACTIVE_ORDER_EXISTS`.
4. Строки корзины + позиции меню (`cart_items ... FOR UPDATE`).
5. Корзина пуста → `409 CART_EMPTY`.
6. Каждая строка: `is_available` и `price_for(size) is not None`; проблемы
   собираются **все сразу** → `409 CART_HAS_UNAVAILABLE_ITEMS` с деталями;
   ничего не создаётся, корзина не меняется.
7. Код (см. выше), `total_amd`.
8. `INSERT orders`, `INSERT order_items` (`unit_price_amd` из текущего меню),
   `INSERT order_events (NULL → NEW)`.
9. `DELETE FROM cart_items WHERE customer_id = :id`.
10. `COMMIT`. 1062 по `uq_orders_day_code` или 1213 → откат и повтор с шага 1
    (до 15 раз), затем `500 INTERNAL_ERROR` с записью в лог; корзина цела.

Окно между чтением `is_available` и коммитом (бариста ставит позицию в
стоп-лист в ту же миллисекунду) осознанно не закрывается блокировкой
`menu_items`: последствие — один уже принятый заказ, который бариста отменит.

## Миграции и сиды

- Alembic, линейная история, файлы `NNNN_<description>.py`; первая —
  `0001_initial_schema` со всеми шестью таблицами.
- Функциональный индекс `uq_orders_day_code` создаётся сырым DDL через
  `op.execute(...)`: autogenerate функциональные индексы не понимает,
  поэтому в `env.py` он исключается из сравнения (`include_object`).
- `seed/menu.json` — **меню как код**: `python -m app.seed` делает upsert по
  `name` (обновляет `category`, `price_*`, `image_url`), **никогда не трогает
  `is_available`** (это поле баристы) и ничего не удаляет (позиция, убранная
  из файла, остаётся в БД, сид пишет предупреждение в лог).
- В контейнере `python -m app.boot` выполняет `alembic upgrade head` и сид при
  `MIGRATE_ON_START=true` / `SEED_ON_START=true` (один контейнер `api`, гонки
  миграций нет). Даунгрейды не автоматизируются: миграции только вперёд.

## Что обязано проверяться тестами против живой MySQL

- Все `CHECK` и `UNIQUE` реально срабатывают (вставка мусора → ошибка БД).
- `uq_orders_day_code`: одинаковый код в одни ереванские сутки → 1062; тот же
  код в 23:59 и 00:01 по Еревану (19:59 / 20:01 UTC) → обе вставки проходят.
- `EXPLAIN` запроса `MAX(code)` использует `uq_orders_day_code`.
- Параллельные оформления 10 клиентов → 10 разных кодов подряд.
- Двойное оформление одного клиента → один заказ + `ACTIVE_ORDER_EXISTS`.
- `A-999` занят → `DAILY_ORDER_LIMIT_REACHED`.
- Гонка «клиент отменяет / бариста начинает» → ровно один выигрывает, одно
  событие.

## Проверено на живой MySQL 8.4.11 (задача B1, 09.10.2026)

- `alembic upgrade head` создаёт шесть таблиц + `alembic_version`; повтор — no-op;
  `alembic check` — «No new upgrade operations detected». DDL, который даёт
  `Base.metadata.create_all` по моделям, совпадает с DDL миграции построчно
  (различается только `AUTO_INCREMENT`), кроме функционального индекса
  (его нет в моделях намеренно).
- **MySQL хранит выражение индекса в нормализованном виде**:
  `UNIQUE KEY uq_orders_day_code ((cast((created_at + interval 4 hour) as date)), code)`
  (`DATE(x)` превращается в `CAST(x AS DATE)`). Запрос `MAX(code)` с
  `DATE(created_at + INTERVAL 4 HOUR)` оптимизатор всё равно сопоставляет с индексом:
  `EXPLAIN` даёт `type=ref`, `key=uq_orders_day_code`. SQL запроса лежит в
  `repositories/orders.py` (`MAX_CODE_FOR_DAY_SQL`) и проверяется тестом.
- Дубликат кода за ереванские сутки — `1062` по `orders.uq_orders_day_code`
  (даже если первый заказ отменён и даже для разных клиентов); 19:59 и 20:01 UTC,
  а также 19:59:59.999999 и 20:00:00 UTC — разные сутки, обе вставки проходят.
- Каждый `CHECK` падает с `3819` и именем ограничения в сообщении, каждый
  `UNIQUE` — `1062`, FK — `1452`/`1451`; `cart_items` каскадно удаляются с клиентом.

### Особенности, которые надо знать (схему пользователя не меняют)

- **`CHECK` по перечислениям регистрозависимы** (с B2/B3): столбцы
  `category/size/status/from_status/to_status/code` — `ascii` + `ascii_bin`, поэтому
  `status = 'new'` и `size = 's'` через сырой SQL дают `3819` (раньше коллация
  `utf8mb4_0900_ai_ci` пропускала их). Миграция `0001` правилась на месте (нигде
  не применялась); имена таблиц и столбцов не менялись. Тесты:
  `test_schema_constraints.py` (регистровые варианты), `test_migrations.py`
  (`test_enum_like_columns_are_ascii_binary`).
- **`ck_orders_code`**: `code REGEXP '^A-[0-9]{3}$' AND code <> 'A-000'` — формат «A-» и
  ровно три цифры проверяет сама БД (`A-abc`, `A-12a`, `a-001` дают `3819`); столбец
  `code` — `ascii_bin`, иначе `REGEXP` нечувствителен к регистру.
- Слишком длинное значение (`size = 'XL'`) отвергается раньше `CHECK`:
  `1406 Data too long`.
- Индексы под FK `menu_item_id` в `cart_items` и `order_items` MySQL создаёт сам
  (имя = имя FK); в моделях они не объявлены, `alembic check` их не считает расхождением.
- Типы: `INT/BIGINT/SMALLINT UNSIGNED` (`db/types.py`), `DATETIME(6)` →
  `UtcDateTime`; `device_id` и `code` — `CHAR ... CHARACTER SET ascii`
  (коллация `ascii_general_ci`: `device_id` нечувствителен к регистру, сервер
  всё равно нормализует в нижний).
- Сид: меню совпадает по `name` через коллацию БД (без учёта регистра и
  диакритики), поэтому `latte` в БД и `Latte` в файле — одна позиция.
- `downgrade()` в `0001` написан (нужен тестам: `downgrade base` → `upgrade head`),
  в проде не используется.

## Проверено на живой MySQL (задачи B2/B3, 09.10.2026)

- Все пункты списка «Что обязано проверяться» выше закрыты автотестами через HTTP:
  `test_checkout_concurrency.py` (10 параллельных оформлений → `A-001..A-010` без
  дублей, по 1 событию на заказ; двойное оформление → 1 заказ + `ACTIVE_ORDER_EXISTS`),
  `test_checkout_api.py` (ереванская полночь, `A-999`, `DAILY_ORDER_LIMIT_REACHED`
  с целой корзиной), `test_status_races.py` (гонка cancel клиента / `IN_PROGRESS`
  баристы: ровно один успех, ровно одно событие).
- Блокировки: строка `customers` (`SELECT ... FOR UPDATE`) берётся и при изменении
  корзины, и при оформлении — они не пересекаются друг с другом у одного клиента.
  Чтения «после блокировки» — блокирующие (`FOR UPDATE`/`FOR SHARE`): иначе
  `REPEATABLE READ` вернул бы старый снимок. `get_customer` завершает транзакцию
  до вызова сервиса, поэтому снимок строится уже после блокировки.
- `ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)` при гонке двух первых запросов
  одного `device_id` создаёт ровно одного клиента (тест на 8 параллельных запросов).
