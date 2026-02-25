import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

from bot.settings import settings


DATA_PATH = Path("/app/data/videos.json")


def parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    # DB columns are TIMESTAMP (without timezone), normalize to naive UTC.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def ensure_id_columns_are_text(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND (
            (table_name = 'videos' AND column_name IN ('id', 'creator_id'))
            OR
            (table_name = 'video_snapshots' AND column_name IN ('id', 'video_id'))
          )
        """
    )

    types = {(r["table_name"], r["column_name"]): r["data_type"] for r in rows}
    needs_migration = any(t != "text" for t in types.values())
    if not needs_migration:
        return

    await conn.execute(
        """
        ALTER TABLE video_snapshots DROP CONSTRAINT IF EXISTS video_snapshots_video_id_fkey;
        ALTER TABLE videos ALTER COLUMN id TYPE TEXT USING id::text;
        ALTER TABLE videos ALTER COLUMN creator_id TYPE TEXT USING creator_id::text;
        ALTER TABLE video_snapshots ALTER COLUMN id TYPE TEXT USING id::text;
        ALTER TABLE video_snapshots ALTER COLUMN video_id TYPE TEXT USING video_id::text;
        ALTER TABLE video_snapshots
            ADD CONSTRAINT video_snapshots_video_id_fkey
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE;
        """
    )


async def load() -> None:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    videos = raw["videos"] if isinstance(raw, dict) and "videos" in raw else raw

    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )

    try:
        await ensure_id_columns_are_text(conn)
        async with conn.transaction():
            for v in videos:
                await conn.execute(
                    """
                    INSERT INTO videos (
                        id, creator_id, video_created_at,
                        views_count, likes_count, comments_count, reports_count
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    str(v["id"]),
                    str(v["creator_id"]),
                    parse_ts(v["video_created_at"]),
                    int(v["views_count"]),
                    int(v["likes_count"]),
                    int(v["comments_count"]),
                    int(v["reports_count"]),
                )

                snapshots = v.get("snapshots") or v.get("video_snapshots") or []
                for s in snapshots:
                    await conn.execute(
                        """
                        INSERT INTO video_snapshots (
                            id, video_id,
                            views_count, likes_count, comments_count, reports_count,
                            delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count,
                            created_at
                        )
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        str(s["id"]),
                        str(v["id"]),
                        int(s["views_count"]),
                        int(s["likes_count"]),
                        int(s["comments_count"]),
                        int(s["reports_count"]),
                        int(s["delta_views_count"]),
                        int(s["delta_likes_count"]),
                        int(s["delta_comments_count"]),
                        int(s["delta_reports_count"]),
                        parse_ts(s["created_at"]),
                    )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(load())
