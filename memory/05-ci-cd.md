# 05. CI/CD (GitHub Actions)

Статус: **Фаза 2: реализовано** (задача D3, 09.10.2026). Спецификация —
Фаза 1, утверждена. Что проверено локально, а что нет — в конце файла.

Структура повторяет Miasin: YAML — только `.github/workflows/ci-cd.yml`,
**вся логика — в скриптах `ci/`**, которые запускаются и руками.

```
ci/
  check-cyrillic.sh   — правило №5 по всему репозиторию (подход — ниже)
  check-i18n.mjs      — паритет ключей en/ru/hy панели + литеральные ключи из кода
  check-shell.sh      — bash -n и shellcheck по ci/*.sh
  lint-backend.sh     — ruff check + ruff format --check (app/backend)
  write-ci-env.sh     — временный .env для compose с СЛУЧАЙНЫМИ паролями (в git паролей нет)
  image-check.sh      — compose config, build api, up -d, ожидание /api/health/ready, down -v
  build-bundle.sh     — собирает app.tar.gz + web.tar.gz и проверяет их раскладку
  deploy.sh           — копирует архивы на сервер по ssh и запускает remote-deploy.sh
  remote-deploy.sh    — выполняется НА сервере (stdin -> bash -s)
  smoke-test.sh       — проверки после деплоя по PUBLIC_BASE_URL
```

## Задания

Триггеры: `push` в `main`, `pull_request`, `workflow_dispatch`. Права
`GITHUB_TOKEN` — `contents: read` на весь файл. Версии actions закреплены на
мажорные (`checkout@v7`, `setup-python@v7`, `setup-node@v7`,
`upload-artifact@v7`, `download-artifact@v8`; только официальные `actions/*`,
сторонних нет), везде `persist-credentials: false`; в `run` не подставляются
`${{ github.event.* }}`, секреты и переменные идут только через `env:` нужных
шагов.

| Задание | Что делает |
|---|---|
| `quality` | ставит ruff (версия из `requirements-dev.txt`); `lint-backend.sh`; `check-cyrillic.sh`; `check-i18n.mjs`; `check-shell.sh` (`REQUIRE_SHELLCHECK=1`); `actionlint` (docker-образ `rhysd/actionlint:1.7.12`) |
| `backend-tests` | service-контейнер `mysql:8.4` (`MYSQL_ALLOW_EMPTY_PASSWORD`, база `ci_test`); `pip install -r requirements-dev.txt`; `alembic upgrade head` на пустой базе; `pytest` (unit + integration против этой MySQL) |
| `build-web` | `npm ci`, `npm run lint`, `npm test`, `npm run build` в `app/web`; проверка `dist/index.html`; артефакт `web-dist` (7 дней) |
| `image` | checkout `74vahan/BrewQ_image` @ `vars.BREWQ_IMAGE_REF` (по умолчанию `main`) в `_image/`; `ci/image-check.sh` с `BACKEND_CONTEXT=$GITHUB_WORKSPACE/app/backend` |
| `deploy` | `needs: [quality, backend-tests, build-web, image]`; только push в `main` или `workflow_dispatch`; checkout `_image/`; скачивает `web-dist`; `build-bundle.sh` (всегда); страж секретов; `deploy.sh`; `smoke-test.sh` |

Python в CI — **3.12**, MySQL — **8.4**: ровно то, что едет в прод; Node — **22 LTS**
(Vite 8 требует >= 20.19).

Параллельность. Общая группа `concurrency` отменяет устаревшие прогоны веток и
PR, но **не прогоны `main`** (`cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`):
в нём может идти деплой. У `deploy` своя группа `brewq-infra-deploy` с
`cancel-in-progress: false`. (В образце Miasin общая группа отменяла и main —
это могло прервать деплой на середине.)

Страж секретов: нет `SERVER_HOST` или `SSH_PRIVATE_KEY` → `::notice`, остальные
шаги деплоя пропускаются, задание остаётся **зелёным** (сервера пока нет —
GCP-аккаунта нет). Архивы при этом всё равно собираются: раскладка проверяется
уже сейчас.

Откат. `workflow_dispatch` разрешён с любого ref (ветка или тег): запуск на
старом теге задеплоит старый код. Панель откатывается ещё и руками —
переключением симлинка (см. ниже). Миграции только вперёд, поэтому миграции
пишутся обратно-совместимыми (сначала добавить, потом использовать, удалять —
отдельным релизом).

## `check-cyrillic.sh` — как отличаются комментарии

Проверяется весь репозиторий (`git ls-files --cached --others --exclude-standard`,
работает и без коммитов), кроме `node_modules`, `dist`, `build`, `.venv`,
`.claude`, `_image`, документации `*.md` и файла `app/web/src/i18n/locales/ru.json`.

1. Тип файла определяется по расширению: `py`, `hash` (sh/yml/toml/txt/Dockerfile/…),
   `slash` (js/ts/tsx/css), `html` (html/svg), `sql`, `none` (json).
2. Из исходника **вырезаются комментарии** с сохранением нумерации строк:
   `#` (Python, shell, YAML — в shell/YAML только после пробела), `//` и
   `/* */` (JS/TS/CSS, в том числе `{/* … */}` в JSX), `<!-- -->` (HTML/SVG),
   `--` и `/* */` (SQL), docstring'и `"""…"""` в Python. Строковые литералы
   при этом отслеживаются: `"http://x"` или `"# …"` не считаются комментарием.
3. Любая кириллица в остатке (код, строки, идентификаторы) — **ошибка**, exit 1.
4. Дополнительно, **только предупреждением** (exit code не меняется, в Actions —
   аннотация): слова, где вместе латиница и кириллица, во всех текстовых файлах,
   включая комментарии, `*.md` и `ru.json`. Так выглядит опечатка с
   похожей буквой в русском слове.

Ограничения: построчная эвристика, не парсер. Кавычка внутри комментария
правой части строки или регулярка с кавычкой могут сбить отслеживание строк до
конца строки; `#` после пробела внутри shell-строки считается комментарием.
Для кода репозитория это не встречается; на ложное срабатывание — переписать
строку или вынести текст в локализацию.

## Почему CI берёт Docker-файлы из BrewQ_image checkout'ом

Compose и Dockerfile принадлежат `BrewQ_image`, код — этому репозиторию. CI
собирает их вместе: публичный `BrewQ_image` клонируется без токена, на
закреплённом `BREWQ_IMAGE_REF`. Так CI реально собирает **тот же** образ,
что поедет на сервер, а правка Dockerfile доезжает обычным деплоем, без
`terraform apply`. Если `BrewQ_image` станет приватным — добавляется секрет
`BREWQ_IMAGE_TOKEN` (fine-grained PAT, только `contents:read`) и параметр
`token:` у двух checkout'ов. Альтернатива и почему отвергнута — `06-decisions.md` (Б14).

## Деплой

Едут **два архива** (`build-bundle.sh`, по умолчанию в `build/bundle/`):

| Архив | Состав | Куда |
|---|---|---|
| `app.tar.gz` | `backend/` (= `app/backend` без `tests/`, кэшей, `.venv`, `.env*`), `docker/` (= `_image/docker`), `media/` (= `app/media`) | `/srv/brewq/app/` — заменяется целиком |
| `web.tar.gz` | содержимое `app/web/dist` | `/srv/brewq/web/releases/<sha>/` |

`build-bundle.sh` после сборки проверяет раскладку (есть `backend/requirements.txt`,
`alembic.ini`, `alembic/`, `app/main.py`, `seed/menu.json`, `docker/docker-compose.yml`,
`docker/backend.Dockerfile`, `media/menu/`; нет тестов, кэшей и `.env`; в
`web.tar.gz` есть `index.html`).

`deploy.sh`: проверяет значения (`APP_ROOT`, `RELEASE_SHA`, … — они подставляются
в команду удалённого shell'а, поэтому допускаются только безопасные символы),
известные хосты из `SSH_KNOWN_HOSTS` (`StrictHostKeyChecking=yes`; без секрета —
`accept-new` с предупреждением), `mkdir -p $APP_ROOT/.incoming`, `scp` двух
архивов туда, затем `ssh … bash -s < ci/remote-deploy.sh`. `RELEASE_SHA` в
workflow — первые 12 символов `github.sha`.

`remote-deploy.sh` (на сервере, без sudo, под `flock`, если он есть):

1. Нет `/srv/brewq/.env` → **падает с объяснением** (файл пишет только
   bootstrap из `BrewQ_image`; деплой секреты не выдумывает).
2. Распаковка `app.tar.gz` в `app.new`, проверка состава, `app` → `app.old`,
   `app.new` → `app`.
3. `BACKEND_CONTEXT=/srv/brewq/app/backend docker compose -p brewq --env-file /srv/brewq/.env -f /srv/brewq/app/docker/docker-compose.yml up -d --build --remove-orphans`.
   Миграции и сид выполняет сам контейнер на старте (`python -m app.boot`).
4. Ждёт `http://127.0.0.1:<BACKEND_PORT>/api/health/ready` до 120 с (порт —
   из `.env`, иначе 8081). Не дождался — печатает `logs --tail 50 api` и
   падает: панель **не переключается**, `app.old` остаётся для разбора. Дождался —
   `app.old` удаляется.
5. Распаковка `web.tar.gz` в `releases/<sha>.tmp`, проверка `index.html`, `mv` в
   `releases/<sha>`, атомарное переключение `ln -sfn … current.tmp && mv -Tf current.tmp current`.
6. Чистка: остаются 5 самых свежих релизов (по времени каталога) и всегда —
   живой (`current`). Архивы из `.incoming` удаляются.

Особенности: `docker`/`curl` запускаются с `</dev/null`, потому что сам скрипт
приходит в `bash -s` через stdin и проглоченные строки сломали бы выполнение;
распаковка с `tar -m`, чтобы время каталога релиза было временем деплоя, а не
временем сборки `dist`.

Откат панели — `ln -sfn /srv/brewq/web/releases/<старый-sha> /srv/brewq/web/current.tmp && mv -Tf /srv/brewq/web/current.tmp /srv/brewq/web/current`.
Откат backend — `workflow_dispatch` на старом теге.

## Smoke-тест (`smoke-test.sh`)

Только `curl`/`grep`/`sed`. `BASE_URL` — `vars.PUBLIC_BASE_URL`, иначе `http://<SERVER_HOST>`.

| Запрос | Ожидание | Что ловит |
|---|---|---|
| `GET /api/health` (до 10 повторов) | 200, `"status":"ok"` | процесс жив |
| `GET /api/health/ready` | 200, `"status":"ready"` | БД доступна |
| `GET /` | 200, `text/html` | панель опубликована |
| `GET /today` | 200, `text/html` | SPA-fallback nginx |
| `GET /api/no-such-route` | 404, JSON `NOT_FOUND` | `/api/` не проваливается в SPA-fallback (порядок `location`) |
| `GET /api/menu` с `X-Device-Id: 00000000-0000-4000-8000-000000000000` | 200, `items` не пуст | сид меню применился (фиксированный UUID → одна служебная строка в `customers`) |
| `GET` первого `image_url` из меню | 200, `image/*` | раздача картинок nginx'ом |

## Секреты и переменные репозитория `74vahan/BrewQ_infra`

Кладёт `BrewQ_image/terraform/scripts/push-github-secrets.sh` после
`terraform apply` (кроме `BREWQ_IMAGE_REF` — вручную, по желанию).

| Имя | Тип | Значение |
|---|---|---|
| `SERVER_HOST` | secret | внешний IP VM |
| `SERVER_USER` | secret | `brewq` |
| `SSH_PRIVATE_KEY` | secret | приватный ключ деплоя из Terraform |
| `SSH_KNOWN_HOSTS` | secret | `ssh-keyscan` сервера (без него — `accept-new` с предупреждением) |
| `APP_ROOT` | variable | `/srv/brewq` |
| `PUBLIC_BASE_URL` | variable | `http://<ip>` или `https://<domain>` |
| `BREWQ_IMAGE_REF` | variable | ветка/тег/sha `BrewQ_image`, по умолчанию `main` |

Пароль баристы и пароли БД в GitHub **не попадают** — они только в
`/srv/brewq/.env` и в state Terraform. В репозитории нет и тестовых паролей:
CI-стек получает случайные (`write-ci-env.sh`), service-контейнер MySQL в
`backend-tests` запускается без пароля.

## Запуск проверок руками

```bash
bash ci/check-cyrillic.sh && node ci/check-i18n.mjs && bash ci/check-shell.sh
bash ci/lint-backend.sh                                   # нужен ruff
IMAGE_DOCKER_DIR=../BrewQ_image/docker BACKEND_PORT=18081 bash ci/image-check.sh
IMAGE_DOCKER_DIR=../BrewQ_image/docker bash ci/build-bundle.sh   # -> build/bundle/
BASE_URL=http://127.0.0.1 bash ci/smoke-test.sh
```

## Что проверено (09.10.2026) и что нет

Локально (Windows + Docker 29.7, Compose 5.4):

- `check-cyrillic.sh` по всему BrewQ_infra — проходит, 0 предупреждений; на
  синтетических файлах ловит кириллицу в строках, идентификаторе с буквой-двойником,
  в HTML-тексте, shell-строке, JSON; пропускает комментарии всех видов,
  docstring'и и `ru.json`.
- `check-i18n.mjs` — проходит (88 ключей x 3 языка), поведение то же, что у
  прежней копии в `app/web/scripts`; `npm run check:i18n` теперь вызывает `ci/check-i18n.mjs`.
- `bash -n` и `shellcheck` (docker `koalaman/shellcheck:stable`) по `ci/*.sh` — чисто.
- `actionlint 1.7.12` по workflow — чисто; YAML разобран парсером.
- `lint-backend.sh` (ruff 0.16.10) — чисто.
- Шаги `backend-tests` против временного `mysql:8.4` (пустой пароль, база
  `ci_test`): `alembic upgrade head` и `pytest` — 412 passed.
- `build-bundle.sh` — собирает оба архива, проверка раскладки проходит.
- `remote-deploy.sh` в контейнере `ubuntu:24.04` на каталоге-имитации
  `/srv/brewq` (`docker` — заглушка, health — локальный http-сервер): без `.env` —
  exit 1 с объяснением и без изменений в `app/`; с `.env` — полная раскладка,
  вызов `docker compose` ровно как в спецификации, `.env` не тронут; чистка
  релизов (KEEP=2) оставляет свежие и живой; API не готов — exit 1, симлинк не
  переключён, `app.old` сохранён; битый архив и неверный `RELEASE_SHA` — отказ.
- `deploy.sh` целиком против настоящего `sshd` в контейнере: с `SSH_KNOWN_HOSTS`,
  с неверным ключом хоста (отказ), без `SSH_KNOWN_HOSTS` (предупреждение), попытки
  shell-инъекции через `RELEASE_SHA`/`APP_ROOT` отклоняются.
- `image-check.sh` с настоящим `BrewQ_image/docker`: config, build, up, ready,
  `down -v` — ок.
- `smoke-test.sh` — против эмулятора nginx (маршрутизация `/`, `/today`,
  `/media/`, проксирование `/api/` на настоящий backend в compose): проходит;
  при недоступном API — падает с понятным сообщением.

**Не проверено до первого push:** сам раннер GitHub (поведение
service-контейнера, `docker run actionlint`, кэши pip/npm, права, версии
actions), реальный `terraform apply`/сервер/nginx/`docker compose` на VM,
`workflow_dispatch`. Локальная ветка названа `master`, workflow срабатывает на
`main` — перед первым push ветку нужно переименовать.
