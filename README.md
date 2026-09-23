# «Пойдём?» — backend MVP

FastAPI-сервис для импорта мероприятий и секций Томска, создания возрастных комнат и
совместного вступления. Код организован по предметным модулям в `backend/src`:

```text
backend/
├── migration/              # Alembic
├── src/
│   ├── activity/           # models, schemas, dao, router
│   ├── classifiers/        # enum-классификаторы
│   ├── common/             # возраст, базовые модели и схемы
│   ├── imports/            # adapters, models, schemas, dao, logic, router
│   ├── room/               # models, schemas, dao, logic, router
│   ├── services/           # отдельный scheduler
│   ├── user/               # models, schemas, dao, dependencies, router
│   ├── config.py
│   ├── database.py
│   ├── exceptions.py
│   └── main.py
├── tests/
├── alembic.ini
├── pyproject.toml
└── uv.lock
```

Импорт хранит связь с первоисточником и hash содержимого, поэтому повторный запуск
идемпотентен.

## Запуск в Docker

```bash
cp .env.example .env
docker compose up --build
```

После запуска доступны:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI: http://localhost:8000/openapi.json
- health check: http://localhost:8000/health

API-контейнер сам выполняет `alembic upgrade head`. Для ручного запуска:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
```

## Локальная разработка с uv

Нужны Python 3.12+, `uv` и PostgreSQL.

```bash
cd backend
uv sync --dev
DATABASE_URL=postgresql+asyncpg://poidem:poidem@localhost:5432/poidem uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://poidem:poidem@localhost:5432/poidem uv run uvicorn src.main:app --reload
```

Проверки:

```bash
uv run ruff check .
uv run pytest -q
```

Интеграционные тесты включаются только с отдельной базой (её схема удаляется после
теста). Из корня репозитория:

```bash
docker compose --profile test up -d db-test
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://poidem:poidem@localhost:5433/poidem_test uv run pytest -q
```

## Импорт

Через CLI:

```bash
uv run python -m src.cli.imports run tomsk_philharmonic
uv run python -m src.cli.imports run tomsk_pfdo
uv run python -m src.cli.imports run aquatika
uv run python -m src.cli.imports run dobro_tomsk
uv run python -m src.cli.imports run five_verst_tomsk_training
uv run python -m src.cli.imports run five_verst_tomsk_volunteer
uv run python -m src.cli.imports run-all
```

Через API доступны понятные ручки `POST /api/v1/admin/imports/events/run`,
`POST /api/v1/admin/imports/courses/run`, `POST /api/v1/admin/imports/sections/run`,
`POST /api/v1/admin/imports/volunteering/run`
и общий запуск `POST /api/v1/admin/imports/run-all`. Список загрузчиков вместе с
последним результатом возвращает `GET /api/v1/admin/imports/sources`. Универсальная
ручка `POST /api/v1/admin/imports/{source_code}/run` также сохранена. Планировщик — отдельный
контейнер и при `PARSER_SCHEDULER_ENABLED=true` запускает импорт ежедневно в 03:00
по Томску. В Uvicorn планировщика нет.

## Источники

| Код | Получение | Состояние |
|---|---|---|
| `tomsk_philharmonic` | Публичная афиша официального сайта Томской филармонии | Рабочий HTML-адаптер |
| `tomsk_pfdo` | HTML и headless Chromium: прокрутка SPA, разбор DOM и перехват JSON-ответов страницы | Chromium и системные библиотеки устанавливаются Docker-образом |
| `aquatika` | HTML официальной страницы расписания | Рабочий HTML-адаптер |
| `dobro_tomsk` | JSON-LD карточек Добро.рф, Chromium для динамического списка | Только конкретные будущие события Томска до 7 дней |
| `five_verst_tomsk_training` | Еженедельное расписание страницы «5 вёрст» | Создаёт конкретные старты на ближайшие 21 день |
| `five_verst_tomsk_volunteer` | Таблица будущих волонтёрских дат «5 вёрст» | Рабочий HTML-адаптер |

Первоначально использовалась афиша Культура.РФ, но её `robots.txt` запрещает
автоматический доступ. Источник заменён на официальный сайт Томской областной
государственной филармонии; его публичная афиша разрешена для загрузки.
Перед запросами выдерживается настраиваемая задержка, используются timeout и
экспоненциальные повторы. CAPTCHA, блокировки и авторизация не обходятся. Если сайт
откажет автоматическому клиенту, импорт завершится контролируемой ошибкой
`PARSER_SOURCE_UNAVAILABLE`; конкретная техническая причина будет в `error.details.reason`.

## Проверка сценария в Swagger

1. Создайте пользователей через `POST /api/v1/dev/users`.
2. Скопируйте UUID нужного пользователя в заголовок `X-Debug-User-Id` всех защищённых
   запросов. Этот механизм существует только в `development` и `test`.
3. Запустите импорт и выберите активность.
4. Создайте комнату через `POST /api/v1/rooms`; время и место возьмутся из активности.
5. Переключите UUID заголовка и выполните прямое вступление либо создайте заявку.

Возраст всегда вычисляется из `birth_date` на текущую дату. Диапазоны, пересекающие
18-летие (например, 16–20), запрещены. Владелец входит во вместимость комнаты и не
может выйти без закрытия/отмены. Вступление блокирует строку комнаты через
`SELECT FOR UPDATE`, что защищает последнее место в PostgreSQL.

## Ограничения MVP

- Нет production-аутентификации: в production debug-заголовок полностью отключён.
- Нет чата, уведомлений, оплаты, карт, отзывов и frontend.
- Парсеры зависят от публичной HTML-разметки; ошибки отдельных записей считаются в
  `ImportRun`, исходные payload и URL сохраняются для диагностики.
- Исчезнувшие записи не удаляются: обычно после `STALE_AFTER_DAYS` они становятся
  `STALE`. Для регулярных расписаний это происходит сразу после успешной проверки
  источника, если слот исчез.
- Playwright запускается только как fallback для динамических страниц ПФДО и Добро.рф.
