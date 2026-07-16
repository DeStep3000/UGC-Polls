# UGC-Polls

Backend для тестового задания "Опросы UGC".

## Что сделано

- Django/DRF-приложение с моделями `Survey`, `Question`, `AnswerOption`, `SurveyAttempt`, `UserAnswer`.
- Демо-опрос по Star Wars: 15 вопросов и по 5 вариантов ответа на каждый вопрос.
- Порядок вопросов и вариантов задается автором через поле `order`.
- Добавлены индексы и уникальные ограничения под большие объемы данных.
- Есть Swagger UI для ручной проверки API.
- Добавлен Redis-кеш для структуры опубликованного опроса и статистики.
- Проект настроен под `uv`, `ruff`, `pytest`, Docker и Docker Compose.

## Запуск локально

```bash
uv sync
uv run python app/manage.py migrate
uv run python app/manage.py runserver 127.0.0.1:8000
```

Если `POSTGRES_HOST` не задан, приложение использует SQLite. Если `REDIS_HOST` не задан, используется локальный in-memory cache, чтобы тесты работали без Redis.

## Запуск в Docker

```bash
docker compose up --build
```

Будет поднято:

- backend: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Postgres: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`

## Проверки

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Как проверить через Swagger

1. Открой `http://127.0.0.1:8000/api/docs/`.
2. Выполни `POST /api/demo-data/`.

Body:

```json
{
  "title": "Звездные войны",
  "username": "respondent"
}
```

В ответе будут `survey_id`, `user_id`, ссылки и 15 вопросов с вариантами.

3. Выполни `GET /api/surveys/{survey_id}/next-question/` и передай `user_id`.
4. Возьми `question.id` и один `option.id` из ответа.
5. Выполни `POST /api/surveys/{survey_id}/answers/`.

Body:

```json
{
  "user_id": 1,
  "question_id": 1,
  "option_id": 1,
  "time_spent_ms": 1500
}
```

6. Еще раз вызови `GET /api/surveys/{survey_id}/next-question/`: должен вернуться следующий вопрос.
7. Выполни `GET /api/surveys/{survey_id}/stats/`: увидишь статистику по ответам.

## Основные endpoint'ы

```http
POST /api/demo-data/
GET /api/surveys/{survey_id}/next-question/?user_id={user_id}
POST /api/surveys/{survey_id}/answers/
GET /api/surveys/{survey_id}/stats/
```

## Redis-кеширование

Redis используется точечно:

- структура опубликованного опроса кешируется на `SURVEY_STRUCTURE_CACHE_TTL_SECONDS`;
- статистика опроса кешируется на `SURVEY_STATS_CACHE_TTL_SECONDS`;
- после нового ответа кеш статистики сбрасывается;
- персональный результат `next-question` целиком не кешируется, потому что он зависит от ответов конкретного пользователя.

Это дает полезный эффект под нагрузкой: вопросы и варианты опроса не нужно каждый раз читать из БД, а часто открываемая статистика не пересчитывается на каждый запрос.

## Нагрузочная проверка

Полные числа из задания (`1 000 000` опросов и `15 000 000` пользователей) локально обычно не поднимают. Для локальной имитации создай меньший, но похожий набор данных:

```bash
docker compose exec backend python manage.py seed_load_data \
  --surveys 1000 \
  --users 10000 \
  --questions-per-survey 15 \
  --options-per-question 5 \
  --attempts 20000 \
  --prefix local_load
```

После этого можно гонять запрос:

```http
GET /api/surveys/{survey_id}/next-question/?user_id={user_id}
```

Через Postman/Newman можно сделать много последовательных запросов, но для настоящей нагрузки лучше использовать `k6`, `Locust` или `JMeter`.

## Пачки разработки

1. Инфраструктура: `pyproject.toml`, `uv.lock`, `.env.example`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
2. Django-основа: `app/manage.py`, `app/config/`.
3. Доменная модель: `app/polls/models.py`, `app/polls/admin.py`, `app/polls/migrations/0001_initial.py`.
4. API: `app/polls/serializers.py`, `app/polls/views.py`, `app/polls/urls.py`.
5. Swagger и демо-данные: `drf-spectacular`, `POST /api/demo-data/`, русские описания ручек.
6. Redis-кеш и нагрузка: `app/polls/cache.py`, `seed_load_data`, Redis в `docker-compose.yml`.
7. Тесты и документация: `app/polls/tests.py`, `README.md`.
