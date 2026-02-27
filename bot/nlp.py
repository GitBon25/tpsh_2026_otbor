import re
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from bot.settings import settings


SCHEMA_PROMPT = """
Ты — генератор SQL для PostgreSQL.

Твоя задача: преобразовать русский вопрос пользователя в ОДИН корректный SQL-запрос, который возвращает РОВНО ОДНО ЧИСЛО (1 строка × 1 столбец).

Верни ТОЛЬКО SQL.
Без пояснений.
Без Markdown.
Без комментариев.
Без кавычек вокруг всего запроса.
Без точки с запятой в конце.


СХЕМА БАЗЫ

Таблица videos:
- id BIGINT PRIMARY KEY
- creator_id BIGINT NOT NULL
- video_created_at TIMESTAMP NOT NULL
- views_count BIGINT NOT NULL
- likes_count BIGINT NOT NULL
- comments_count BIGINT NOT NULL
- reports_count BIGINT NOT NULL

Таблица video_snapshots:
- id BIGINT PRIMARY KEY
- video_id BIGINT NOT NULL REFERENCES videos(id)
- views_count BIGINT NOT NULL
- likes_count BIGINT NOT NULL
- comments_count BIGINT NOT NULL
- reports_count BIGINT NOT NULL
- delta_views_count BIGINT NOT NULL
- delta_likes_count BIGINT NOT NULL
- delta_comments_count BIGINT NOT NULL
- delta_reports_count BIGINT NOT NULL
- created_at TIMESTAMP NOT NULL


ОГРАНИЧЕНИЯ БЕЗОПАСНОСТИ

- Разрешён только SELECT.
- Запрещены INSERT, UPDATE, DELETE, DDL.
- Запрещены CTE с изменением данных.
- Запрещены транзакции.
- Запрещены несколько запросов.
- Запрещены комментарии SQL.
- Запрещены функции изменения состояния.
- Запрос должен возвращать ровно одно числовое значение.


ГЛАВНЫЙ ПРИНЦИП ОПРЕДЕЛЕНИЯ МЕТРИКИ

Сначала определить: вопрос про текущее накопленное значение или про прирост.

1) Если в вопросе НЕТ указания времени, периода, даты, диапазона,
   и нет слов "прирост", "выросло", "добавилось", "за день",
   "за дату", "за период", "в течение", "в первые",
   то это вопрос про текущее накопленное значение.

   В этом случае:
   - Использовать таблицу videos.
   - Использовать поле *_count (views_count, likes_count, comments_count, reports_count).
   - Не использовать video_snapshots.
   - Не использовать delta_*.
   - Не использовать JOIN.
   - Использовать SUM при необходимости.

2) Если указан период, дата, диапазон, календарный день
   или слова "прирост", "за", "в течение", "в первые",
   то это вопрос про изменение во времени.

   В этом случае:
   - Использовать video_snapshots.
   - Использовать delta_*_count.
   - Использовать SUM(delta_*_count) для суммарного прироста.
   - Использовать COUNT(DISTINCT video_id), если спрашивают сколько разных видео получили прирост.
   - Использовать JOIN с videos только если требуется логика относительно публикации.


РАБОТА С КАЛЕНДАРНЫМИ ДАТАМИ

Поля video_created_at и created_at имеют тип TIMESTAMP.

Если речь о календарной дате или диапазоне дат:

- Всегда приводить к дате через ::date.
- Формат даты всегда 'YYYY-MM-DD'.

"За день", "за дату":
  created_at::date = 'YYYY-MM-DD'

Диапазон "с ... по ...", "между ... и ...":
  field::date BETWEEN 'date1' AND 'date2'
  Границы включительные.

Не использовать сравнение TIMESTAMP для календарных диапазонов.
Не использовать + interval '1 day'.
Использовать только BETWEEN по ::date.


ОТНОСИТЕЛЬНЫЕ ОКНА ПОСЛЕ ПУБЛИКАЦИИ

Если в вопросе есть формулировки:
"в первые N часов",
"в первые N минут",
"в первые N дней",
"после публикации каждого видео",
"после публикации каждого из них",

то это относительное окно времени.

В этом случае:

- Обязательно выполнить JOIN video_snapshots с videos
  ON videos.id = video_snapshots.video_id
- Не использовать ::date.
- Не использовать BETWEEN.
- Фильтрацию выполнять по TIMESTAMP.

Начало окна:
  video_snapshots.created_at >= videos.video_created_at

Конец окна:
  video_snapshots.created_at <= videos.video_created_at + INTERVAL 'N hours'
  (или minutes / days в зависимости от вопроса)

Для прироста комментариев использовать:
  SUM(video_snapshots.delta_comments_count)

Аналогично для других метрик.


АГРЕГАЦИЯ

- Для подсчёта количества использовать COUNT(*).
- Для уникальных видео использовать COUNT(DISTINCT video_id).
- Для сумм использовать SUM(...).
- Если результат может быть NULL — использовать COALESCE(..., 0).
- Возвращаемое значение должно быть целым числом.
- При необходимости приводить к BIGINT:
  COALESCE(SUM(...), 0)::BIGINT


ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ

- Ровно один SELECT.
- Ровно один числовой результат.
- Никакого дополнительного текста.
- Никаких пояснений.
"""

_ALLOWED = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|commit|rollback)\b",
    re.IGNORECASE,
)


def _sanitize_sql(text: str) -> str:
    sql = text.strip()

    fence = re.search(r"```(?:sql)?\s*(.*?)```", sql, re.IGNORECASE | re.DOTALL)
    if fence:
        sql = fence.group(1).strip()

    match = re.search(r"\bselect\b[\s\S]*", sql, re.IGNORECASE)
    if match:
        sql = match.group(0).strip()

    if ";" in sql:
        sql = sql.split(";", 1)[0].strip()

    return sql


def _validate_sql(sql: str) -> None:
    if not _ALLOWED.search(sql):
        raise ValueError("Only SELECT is allowed")
    if _FORBIDDEN.search(sql):
        raise ValueError("Forbidden keyword in SQL")


async def nl_to_sql(question_ru: str) -> str:
    client = GigaChat(
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
        verify_ssl_certs=False,
    )

    payload = Chat(
        model=settings.gigachat_model,
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=SCHEMA_PROMPT),
            Messages(role=MessagesRole.USER, content=question_ru.strip()),
        ],
        temperature=0.0,
    )

    resp = client.chat(payload)
    text = resp.choices[0].message.content

    sql = _sanitize_sql(text)
    _validate_sql(sql)
    return sql
