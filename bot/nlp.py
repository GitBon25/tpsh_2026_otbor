import re
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from bot.settings import settings


SCHEMA_PROMPT = """
Ты — генератор SQL для PostgreSQL. 
Твоя задача: преобразовать русский вопрос пользователя в ОДИН корректный SQL-запрос, который вернёт РОВНО ОДНО ЧИСЛО (1 строка × 1 столбец). 
Верни ТОЛЬКО SQL, без пояснений, без кавычек вокруг всего запроса, без Markdown и без лишнего текста.

Схема базы:

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

Ограничения безопасности:
- Разрешён ТОЛЬКО SELECT.
- Запрещены INSERT/UPDATE/DELETE/DDL, CTE с изменением данных, транзакции, несколько запросов, точка с запятой внутри, комментарии SQL.
- Запрещены функции, которые могут менять состояние (например, pg_sleep).
- Запрос должен возвращать одно числовое значение. Нельзя возвращать таблицу или несколько колонок.

Главная цель:
- Вернуть точный ответ по данным в БД. Не придумывай значения, не используй константы вместо вычислений.

Правила выбора таблиц:
1) Если вопрос про количество видео/видео автора/видео за период создания — используй videos и поле video_created_at.
2) Если вопрос про «прирост», «выросло», «добавилось», «за день», «за дату», «за период» по метрикам (просмотры/лайки/комментарии/репорты) — используй video_snapshots и сумму delta_*_count (а не views_count).
3) Если вопрос про «сколько разных видео получали новые просмотры/лайки/комментарии/репорты» за дату/период — используй COUNT(DISTINCT video_id) из video_snapshots с условием delta_*_count > 0.
4) Если вопрос про текущее общее значение метрики у видео/автора (например «сколько всего просмотров у видео/у автора») и нет слов «прирост/выросло/за период» — используй videos.*_count (агрегация SUM по videos при необходимости).

Правила работы с датами и периодами (КРИТИЧНО):
- Поля video_created_at и created_at имеют тип TIMESTAMP.
- Любые сравнения с календарной датой выполняй через приведение к дате: (video_created_at::date) или (created_at::date).
- Формат даты в SQL всегда 'YYYY-MM-DD'.

Определение «за дату / за день / за 28 ноября 2025»:
- Это календарный день. Фильтр делай только так:
  created_at::date = 'YYYY-MM-DD'  (для snapshot-метрик)
  video_created_at::date = 'YYYY-MM-DD' (для даты публикации видео)

Определение диапазона «с … по …»:
- Если в вопросе явно сказано «с <дата1> по <дата2>» или «между <дата1> и <дата2>», то ОБЕ границы включительны.
- Реализуй включительность только через BETWEEN по ::date:
  field::date BETWEEN 'date1' AND 'date2'
- НЕ используй сравнения по TIMESTAMP вида field >= date1 AND field <= date2, чтобы не ошибиться на времени суток.
- НЕ используй end_date + interval '1 day' — только BETWEEN по ::date.

Диапазон «за период» без указания границ:
- Если нет явных дат/границ, не выдумывай диапазон. Вычисляй без временного фильтра.

Нормализация дат из русского текста:
- Если пользователь пишет дату словами (например «1 ноября 2025»), преобразуй в '2025-11-01'.
- Если пользователь пишет диапазон вроде «с 1 по 5 ноября 2025», то год относится ко всем датам в диапазоне.
- Если пользователь пишет «с 28 ноября по 2 декабря 2025», корректно проставь месяцы и год для обеих границ.

Ограничения на агрегации:
- Для подсчётов используй COUNT(*), COUNT(DISTINCT ...).
- Для сумм приростов используй SUM(delta_*_count).
- Если результат может быть NULL (например SUM по пустому набору), верни 0 через COALESCE(..., 0).
- Возвращаемое значение должно быть целым числом. Используй явное приведение к BIGINT при необходимости: COALESCE(SUM(...), 0)::BIGINT.

Типовые условия:
- «новые просмотры/лайки/комментарии/репорты» означает delta_*_count > 0.
- «не получали новых» означает delta_*_count = 0 (или отсутствие записей — тогда 0 через COALESCE).

Правила для окон "после публикации":
- Если вопрос содержит формулировки вида "за первые N часов/минут/дней после публикации каждого видео" или "после публикации каждого из них", то это относительное окно времени.
- В таких запросах ОБЯЗАТЕЛЕН JOIN video_snapshots с videos по videos.id = video_snapshots.video_id.
- Начало окна всегда videos.video_created_at.
- Конец окна = videos.video_created_at + INTERVAL '<N> hours' (или minutes/days).
- Фильтрация окна выполняется по TIMESTAMP без приведения к ::date:
  video_snapshots.created_at >= videos.video_created_at
  AND video_snapshots.created_at < videos.video_created_at + INTERVAL '<N> hours'
- Для "прирост комментариев" используй SUM(video_snapshots.delta_comments_count), для просмотров — SUM(delta_views_count), и т.д.
- Итог всегда одно число, NULL заменять на 0: COALESCE(SUM(...), 0).

Технические требования к выходу:
- Ровно один SQL SELECT.
- Без ; в конце.
- Без лишних пробелов/пустых строк — но это не критично.
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
