import asyncio
import json
from pathlib import Path

import asyncpg

from bot.settings import settings


DATA_PATH = Path("/app/data/videos.json")


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
                    int(v["id"]),
                    int(v["creator_id"]),
                    v["video_created_at"],
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
                        int(s["id"]),
                        int(v["id"]),
                        int(s["views_count"]),
                        int(s["likes_count"]),
                        int(s["comments_count"]),
                        int(s["reports_count"]),
                        int(s["delta_views_count"]),
                        int(s["delta_likes_count"]),
                        int(s["delta_comments_count"]),
                        int(s["delta_reports_count"]),
                        s["created_at"],
                    )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(load())