# 03. API (контракт)

Статус: **Фаза 1: утверждено** (09.10.2026). Этот файл — **источник истины**
для backend, веб-панели и `BrewQ_android`. При расхождении побеждает документ;
изменение контракта — сначала здесь, потом в коде всех потребителей.

## Общее

- Базовый путь **`/api`**, JSON, UTF-8. Наружу — через хостовый nginx.
- Время — ISO 8601 UTC с `Z`, **всегда шесть знаков дроби**:
  `"2026-10-09T08:15:30.123456Z"` (`"…:30.000000Z"`, если микросекунд нет).
  Клиенты показывают его в локальном времени устройства/браузера.
- Деньги — целые AMD (`*_amd`), форматирование — на клиенте.
- Размеры `"S" | "M" | "L"`, категории `"coffee" | "tea" | "cake"`, статусы
  `"NEW" | "IN_PROGRESS" | "READY" | "PICKED_UP" | "CANCELLED"` — дословно как
  в БД. Клиенты обязаны переживать **неизвестное** значение (откат к дефолту,
  а не падение).
- Тела запросов валидируются Pydantic с `extra="forbid"`: лишнее поле → 400.
- Имена меню приходят только на английском; подписи категорий, размеров,
  статусов и ошибок — i18n самих приложений (en/ru/hy).
- `image_url` — относительный путь (`/media/menu/latte.webp`) или `null`;
  клиент разрешает его относительно origin API. `null` → заглушка категории.

## Формат ошибок (подтверждён)

```json
{ "error": { "code": "CART_HAS_UNAVAILABLE_ITEMS", "message": "Some cart items cannot be ordered", "details": { } } }
```

- `code` — машиночитаемый; клиенты переводят **по `code`**, `message`
  (английский, для логов) пользователю не показывают.
- `details` — всегда объект (пустой `{}`, если нечего сказать).
- Нечисловой/неположительный id в пути (`/orders/abc`, `/cart/items/0`), неверный
  `scope`, `limit`/`before_id` вне границ — `400 VALIDATION_ERROR`.
- Ответы nginx (502/504/429) могут прийти не JSON — клиенты обязаны не
  падать на не-конверте (`UNKNOWN`).

### Коды ошибок

| HTTP | `code` | Когда | `details` |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | тело/параметры не прошли валидацию (в т.ч. то, что FastAPI отдал бы 422) | `{"fields":[{"field":"qty","issue":"less_than_equal"}]}` |
| 400 | `DEVICE_ID_MISSING` | нет `X-Device-Id` на клиентском эндпоинте | `{}` |
| 400 | `DEVICE_ID_INVALID` | `X-Device-Id` не UUID v4 | `{}` |
| 400 | `SIZE_NOT_OFFERED` | у позиции нет цены для этого размера | `{"menu_item_id":3,"size":"S","offered":["M"]}` |
| 401 | `BARISTA_INVALID_PASSWORD` | неверный пароль при входе | `{}` |
| 401 | `BARISTA_UNAUTHORIZED` | нет/битый/просроченный токен баристы | `{}` |
| 400 | `HTTP_ERROR` | прочая 4xx-ошибка фреймворка без своего кода (не 404/405); статус HTTP сохраняется | `{}` |
| 404 | `NOT_FOUND` | неизвестный маршрут под `/api` | `{}` |
| 404 | `MENU_ITEM_NOT_FOUND` | нет такой позиции | `{"menu_item_id":99}` |
| 404 | `CART_ITEM_NOT_FOUND` | нет такой строки **в своей** корзине | `{"cart_item_id":7}` |
| 404 | `ORDER_NOT_FOUND` | нет заказа **или он чужой** (существование не раскрываем) | `{"order_id":42}` |
| 405 | `METHOD_NOT_ALLOWED` | метод не поддержан | `{}` |
| 409 | `MENU_ITEM_UNAVAILABLE` | добавление в корзину позиции из стоп-листа | `{"menu_item_id":3}` |
| 409 | `CART_QTY_LIMIT_EXCEEDED` | строка корзины стала бы > 20 | `{"max":20,"current":18}` |
| 409 | `CART_EMPTY` | оформление пустой корзины | `{}` |
| 409 | `CART_HAS_UNAVAILABLE_ITEMS` | в корзине позиции из стоп-листа / без цены размера | `{"items":[{"cart_item_id":7,"menu_item_id":3,"name":"Latte","size":"L","reason":"unavailable"}]}`, `reason ∈ {"unavailable","size_not_offered"}` |
| 409 | `ACTIVE_ORDER_EXISTS` | у клиента уже есть заказ в NEW/IN_PROGRESS/READY | `{"order_id":42,"code":"A-007","status":"READY"}` |
| 409 | `DAILY_ORDER_LIMIT_REACHED` | за ереванские сутки уже выдан `A-999` | `{"limit":999}` |
| 409 | `ORDER_NOT_CANCELLABLE` | клиент отменяет не из `NEW` | `{"status":"IN_PROGRESS"}` |
| 409 | `INVALID_STATUS_TRANSITION` | бариста просит недопустимый переход | `{"from":"READY","to":"IN_PROGRESS","allowed":["PICKED_UP"]}` |
| 429 | `RATE_LIMITED` | лимит nginx (JSON-тело отдаёт сам nginx) | `{}` |
| 500 | `INTERNAL_ERROR` | непойманная ошибка; в т.ч. оформление не удалось после всех повторов из-за гонки (корзина цела, повторить можно) | `{}` |
| 503 | `SERVICE_UNAVAILABLE` | `/api/health/ready`: БД недоступна | `{}` |

## Аутентификация

### Клиент — `X-Device-Id`

- Обязателен на всех клиентских эндпоинтах (всё под `/api`, кроме
  `/api/health*` и `/api/barista/*`).
- Формат — UUID v4 (версия 4, вариант RFC 4122); регистр не важен, сервер
  нормализует в нижний. Иначе `DEVICE_ID_INVALID`.
- Первый запрос с новым `device_id` создаёт `customers` (upsert).

### Бариста — пароль → подписанный токен

- `POST /api/barista/login` с `{"password":"..."}`. Сервер сравнивает с
  `BARISTA_PASSWORD` из `.env` через `hmac.compare_digest`.
- Успех → JWT HS256, ключ `BARISTA_TOKEN_SECRET`, claims
  `{"sub":"barista","iat","exp","pwv"}`, срок `BARISTA_TOKEN_TTL_HOURS`
  (по умолчанию 12 — одна смена). `pwv` = первые 16 hex от
  `HMAC-SHA256(BARISTA_TOKEN_SECRET, BARISTA_PASSWORD)`: смена пароля в `.env`
  + перезапуск `api` мгновенно гасит все выданные токены; сам пароль (и даже
  его простой хэш) в токен не попадает.
- Остальные `/api/barista/*` — заголовок `Authorization: Bearer <token>`.
  Любая проблема с токеном → `401 BARISTA_UNAUTHORIZED`.
- Перебор пароля режет nginx: `limit_req` на `= /api/barista/login`
  5 запросов/мин с IP, burst 5, ответ `429 RATE_LIMITED`.
- Таблиц нет, состояния на сервере нет. «Выход» = панель выбрасывает токен.

## Эндпоинты

### Служебные (без аутентификации)

| Метод | Путь | Ответ |
|---|---|---|
| GET | `/api/health` | `200 {"status":"ok"}` — процесс жив, БД не трогает |
| GET | `/api/health/ready` | `200 {"status":"ready"}` или `503 SERVICE_UNAVAILABLE` — `SELECT 1` в БД; его ждут compose healthcheck и деплой |

### Общие формы ответов

`MenuItem`:
```json
{ "id": 3, "name": "Latte", "category": "coffee",
  "sizes": [ {"size":"S","price_amd":1100}, {"size":"M","price_amd":1300}, {"size":"L","price_amd":1500} ],
  "is_available": true, "image_url": "/media/menu/latte.webp" }
```
`sizes` — только предлагаемые размеры, в порядке S, M, L (позиция с одной
ценой → один элемент `M`; клиент тогда не показывает выбор размера).

`Cart`:
```json
{ "items": [ { "id": 7, "menu_item_id": 3, "name": "Latte", "image_url": "/media/menu/latte.webp",
               "size": "M", "qty": 2, "unit_price_amd": 1300, "line_total_amd": 2600,
               "is_available": true, "problem": null } ],
  "total_amd": 2600, "can_checkout": true }
```
Цены корзины — **текущие** из меню; `problem ∈ {null,"unavailable","size_not_offered"}`
(если одновременно и стоп-лист, и нет цены — `"unavailable"`);
`unit_price_amd` и `line_total_amd` равны `null` **только** при
`problem == "size_not_offered"` (цены этого размера в меню больше нет; для
`"unavailable"` цена известна и показывается);
`total_amd` считается по строкам без проблем; `can_checkout` = корзина не
пуста и проблем нет. Порядок строк — по `id`.

`Order` (клиент):
```json
{ "id": 42, "code": "A-007", "status": "IN_PROGRESS", "total_amd": 2600,
  "created_at": "...Z", "updated_at": "...Z", "can_cancel": false,
  "items": [ { "menu_item_id": 3, "name": "Latte", "size": "M", "qty": 2, "unit_price_amd": 1300, "line_total_amd": 2600 } ] }
```
`can_cancel` = `status == "NEW"`. `BaristaOrder` = `Order` без `can_cancel`
плюс `"customer_name": "Ani" | null` и `"allowed_transitions": ["READY","CANCELLED"]`
(панель рисует кнопки только из этого списка).

### Клиент (требует `X-Device-Id`)

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| GET | `/api/menu` | — | `200 {"items":[MenuItem]}` — все позиции, **включая** стоп-лист (`is_available:false`, показываются неактивными); порядок: coffee, tea, cake, внутри — по `name` |
| GET | `/api/me` | — | `200 {"name": "Ani" \| null}` |
| PUT | `/api/me` | `{"name": "Ani" \| null}` | `200 {"name": ...}`; `name` обрезается по краям, 1..40 символов, без управляющих; `null` или пустая строка → NULL |
| GET | `/api/cart` | — | `200 Cart` |
| POST | `/api/cart/items` | `{"menu_item_id":3,"size":"M","qty":1}` (`qty` 1..20, по умолчанию 1) | `200 Cart`; та же позиция+размер → `qty` суммируется. Ошибки: `MENU_ITEM_NOT_FOUND`, `MENU_ITEM_UNAVAILABLE`, `SIZE_NOT_OFFERED`, `CART_QTY_LIMIT_EXCEEDED` |
| PATCH | `/api/cart/items/{cart_item_id}` | `{"qty":3}` (1..20) | `200 Cart`; `CART_ITEM_NOT_FOUND` |
| DELETE | `/api/cart/items/{cart_item_id}` | — | `200 Cart`; `CART_ITEM_NOT_FOUND` |
| DELETE | `/api/cart` | — | `200 Cart` (пустая) |
| POST | `/api/orders` | — (тело не нужно; `{}` допустим) | `201 Order` (статус `NEW`), корзина очищена. Ошибки: `ACTIVE_ORDER_EXISTS`, `CART_EMPTY`, `CART_HAS_UNAVAILABLE_ITEMS`, `DAILY_ORDER_LIMIT_REACHED` |
| GET | `/api/orders/current` | — | `200 {"order": Order \| null}` — активный заказ (NEW/IN_PROGRESS/READY) или `null` |
| GET | `/api/orders/{id}` | — | `200 Order` своего заказа в любом статусе; чужой/нет → `404 ORDER_NOT_FOUND` |
| GET | `/api/orders?limit=20&before_id=123` | — | `200 {"items":[Order], "next_before_id": 101 \| null}` — история, новые сверху, keyset по `id`; `limit` 1..50 |
| POST | `/api/orders/{id}/cancel` | — | `200 Order` (`CANCELLED`); только из `NEW` → иначе `409 ORDER_NOT_CANCELLABLE` |

Изменить размер строки корзины = удалить строку и добавить заново.

Повтор «Оформить» (двойное нажатие, ретрай после таймаута) безопасен без
idempotency-ключа: второй запрос получает `ACTIVE_ORDER_EXISTS` с `order_id`,
и клиент просто открывает этот заказ.

### Бариста

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| POST | `/api/barista/login` | `{"password":"..."}` | `200 {"token":"...","expires_at":"...Z"}`; `401 BARISTA_INVALID_PASSWORD` |
| GET | `/api/barista/orders?scope=active` | — | `200 {"items":[BaristaOrder]}` — все NEW/IN_PROGRESS/READY, **старые сверху** (очередь) |
| GET | `/api/barista/orders?scope=today` | — | `200 {"items":[BaristaOrder]}` — все заказы текущих ереванских суток в любом статусе, новые сверху |
| POST | `/api/barista/orders/{id}/status` | `{"to":"IN_PROGRESS"}` | `200 BaristaOrder`; `to ∈ {IN_PROGRESS, READY, PICKED_UP, CANCELLED}` (другое значение, включая `NEW`, — `400 VALIDATION_ERROR`); недопустимо → `409 INVALID_STATUS_TRANSITION` (в `from` — **актуальный** статус); нет заказа → `404 ORDER_NOT_FOUND` |
| GET | `/api/barista/menu` | — | `200 {"items":[MenuItem]}` — всё меню, тот же порядок |
| PATCH | `/api/barista/menu/{id}` | `{"is_available": false}` (единственное разрешённое поле) | `200 MenuItem`; `404 MENU_ITEM_NOT_FOUND` |

`scope` по умолчанию `active`; другое значение — `400 VALIDATION_ERROR`. «Сегодня» —
по ереванским суткам (граница 20:00 UTC) относительно времени сервера. Явный `to` (а не «следующий шаг») делает
повторное нажатие безопасным: второй `IN_PROGRESS → IN_PROGRESS` честно
получает 409, а не продвигает заказ ещё на шаг.

## Поллинг

- Android: пока открыт экран заказа и приложение на переднем плане —
  `GET /api/orders/{id}` раз в 5 секунд (следующий запрос — через 5 с после
  ответа, без наложения). Остановка на `PICKED_UP`/`CANCELLED`. При старте
  приложения — `GET /api/orders/current`, чтобы восстановить активный заказ.
- Панель: `GET /api/barista/orders?scope=active` раз в 5 секунд.
- Нагрузка: один индексный запрос на опрос; nginx лимитирует `/api/` 10 r/s
  с IP, burst 20 — с запасом для поллинга.

## Чего нет в контракте

CRUD меню (меню = `seed/menu.json`), загрузка картинок, оплата, push,
регистрация, учётные записи барист, idempotency-ключи.
