# «Пойдём?» — backend MVP

FastAPI-сервис для импорта мероприятий и секций Томска, создания возрастных комнат и
совместного вступления. Архитектура разделена на HTTP API (`app/api`), бизнес-правила
(`age.py`, `room_service.py`), асинхронные SQLAlchemy-модели и независимые адаптеры
источников (`app/imports`). Импорт хранит связь с первоисточником и hash содержимого,
поэтому повторный запуск идемпотентен.

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
uv sync --dev
cp .env.example .env
# замените db в DATABASE_URL на localhost
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Проверки:

```bash
uv run ruff check .
uv run pytest -q
```

Интеграционные тесты БД включаются только с отдельной базой (схема в ней удаляется
после теста):

```bash
TEST_DATABASE_URL=postgresql+asyncpg://poidem:poidem@localhost:5432/poidem_test uv run pytest -q
```

## Импорт

Через CLI:

```bash
uv run python -m app.cli.imports run culture_ru
uv run python -m app.cli.imports run tomsk_pfdo
uv run python -m app.cli.imports run aquatika
uv run python -m app.cli.imports run-all
```

Или через `POST /api/v1/admin/imports/{source_code}/run`. Планировщик — отдельный
контейнер и при `PARSER_SCHEDULER_ENABLED=true` запускает импорт ежедневно в 03:00
по Томску. В Uvicorn планировщика нет.

## Источники

| Код | Получение | Состояние |
|---|---|---|
| `culture_ru` | JSON-LD официальной афиши, fallback на публичные HTML-ссылки | Рабочий HTML-адаптер |
| `tomsk_pfdo` | публичная страница регионального навигатора | Рабочий HTML-адаптер; разметка SPA может меняться |
| `aquatika` | HTML официальной страницы расписания | Рабочий HTML-адаптер |

У Культура.РФ существует предпочтительный Export API 2.5, но он требует партнёрский
API-ключ. Поэтому MVP не пытается обходить авторизацию и использует публичную афишу.
Перед запросами выдерживается настраиваемая задержка, используются timeout и
экспоненциальные повторы. CAPTCHA, блокировки и авторизация не обходятся. Если сайт
откажет автоматическому клиенту, импорт завершится контролируемой ошибкой
`PARSER_SOURCE_UNAVAILABLE`.

## Проверка сценария в Swagger

1. Создайте пользователей через `POST /api/v1/dev/users`.
2. Скопируйте UUID нужного пользователя в заголовок `X-Debug-User-Id` всех защищённых
   запросов. Этот механизм существует только в `development` и `test`.
3. Запустите импорт и выберите активность.
4. Создайте комнату через `POST /api/v1/rooms`, передав время с часовым поясом.
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
- Исчезнувшие записи не удаляются: после `STALE_AFTER_DAYS` они становятся `STALE`.
- Playwright не добавлен: текущие источники отдают пригодный HTML; без необходимости
  браузерный runtime не запускается.
