import asyncpg
from bot.settings import settings


class Database:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
            min_size=1,
            max_size=10,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def fetch_number(self, sql: str) -> int:
        if not self._pool:
            raise RuntimeError("DB pool не инициализирован")
        async with self._pool.acquire() as conn:
            val = await conn.fetchval(sql)
            if val is None:
                return 0
            try:
                return int(val)
            except Exception:
                return int(float(val))