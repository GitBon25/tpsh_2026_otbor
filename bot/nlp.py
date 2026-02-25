import re
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from bot.settings import settings


SCHEMA_PROMPT = """
Ты преобразуешь русский вопрос пользователя в один SQL-запрос для PostgreSQL.

Формат ответа (строго):
- Верни ровно один SQL-запрос.
- Запрос должен начинаться с SELECT.
- Верни только SQL: без пояснений, без Markdown, без code fences, без комментариев.
- Только один statement.
- Без точки с запятой в конце.
- Запрос должен возвращать ровно одно число (1 строка, 1 столбец).

Схема БД:
Таблица videos:
- id (TEXT, PK)
- creator_id (TEXT)
- video_created_at (TIMESTAMP)
- views_count (BIGINT)
- likes_count (BIGINT)
- comments_count (BIGINT)
- reports_count (BIGINT)

Таблица video_snapshots:
- id (TEXT, PK)
- video_id (TEXT, FK -> videos.id)
- views_count, likes_count, comments_count, reports_count (BIGINT)
- delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count (BIGINT)
- created_at (TIMESTAMP) — время замера

Правила:
1) Разрешен только SELECT.
2) Используй агрегаты COUNT / SUM, когда это нужно.
3) Для вопросов про "прирост/выросло за дату/день" используй SUM(delta_*_count) из video_snapshots и фильтр по created_at::date.
4) Для вопроса "сколько разных видео получали новые просмотры за дату" используй COUNT(DISTINCT video_id), условие delta_views_count > 0 и фильтр по дате.
5) Для диапазона дат "с ... по ... включительно" используй BETWEEN по ::date с включенными границами.
6) Даты в SQL пиши строго в формате 'YYYY-MM-DD'.
7) Запрещены INSERT/UPDATE/DELETE/DDL.

Примеры:
Вопрос: Сколько всего видео есть в системе?
Ответ: SELECT COUNT(*) FROM videos
Вопрос: Сколько просмотров приросло за 2025-08-20?
Ответ: SELECT COALESCE(SUM(delta_views_count), 0) FROM video_snapshots WHERE created_at::date = '2025-08-20'
Вопрос: Какой суммарный прирост комментариев получили все видео за первые 3 часа после публикации каждого из них?
Ответ: SELECT COALESCE(SUM(vs.delta_comments_count), 0) FROM video_snapshots vs JOIN videos v ON v.id = vs.video_id WHERE vs.created_at >= v.video_created_at AND vs.created_at < v.video_created_at + INTERVAL '3 hour'
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
