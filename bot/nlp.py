import re
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from bot.settings import settings


SCHEMA_PROMPT = """
Ты преобразуешь русский вопрос пользователя в SQL запрос для PostgreSQL.

Схема БД:

Таблица videos:
- id (BIGINT, PK)
- creator_id (BIGINT)
- video_created_at (TIMESTAMP)
- views_count (BIGINT)
- likes_count (BIGINT)
- comments_count (BIGINT)
- reports_count (BIGINT)

Таблица video_snapshots:
- id (BIGINT, PK)
- video_id (BIGINT, FK -> videos.id)
- views_count, likes_count, comments_count, reports_count
- delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count
- created_at (TIMESTAMP) — время замера

Правила:
1) Верни ТОЛЬКО ОДИН SQL-запрос. Никакого текста/Markdown.
2) Запрос должен возвращать ровно ОДНО число (1 строка, 1 столбец).
3) Разрешены только SELECT и агрегаты COUNT / SUM (и их комбинации).
4) Если вопрос про "прирост/выросло" за дату/день — используй SUM(delta_*_count) из video_snapshots и фильтр created_at::date.
5) Если вопрос "сколько разных видео получали новые просмотры" за дату —
   COUNT(DISTINCT video_id) из video_snapshots, delta_views_count > 0, фильтр created_at::date.
6) Если вопрос про диапазон дат "с ... по ... включительно" — BETWEEN по ::date, границы включительно.
7) Даты в SQL пиши строго в формате 'YYYY-MM-DD'.
8) Никаких INSERT/UPDATE/DELETE/DDL, никаких нескольких запросов.
"""

_ALLOWED = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|commit|rollback)\b",
    re.IGNORECASE,
)


def _sanitize_sql(text: str) -> str:
    sql = text.strip()
    sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
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
        verify_ssl=False,
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