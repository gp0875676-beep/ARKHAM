# db/connection.py — asyncpg connection pool singleton.
"""Async Postgres pool. Use `await db.fetch(...)` / `await db.execute(...)`."""
import asyncpg

from config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


class Database:
    """Thin wrapper around asyncpg.create_pool."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.pool = None

    async def connect(self) -> None:
        if not self.settings.database_url:
            log.warning("DATABASE_URL not set. DB features disabled.")
            return
        try:
            self.pool = await asyncpg.create_pool(
                self.settings.database_url, 
                min_size=1, 
                max_size=5
            )
            log.info("DB pool connected.")
        except Exception as e:
            log.error("DB connection failed: {}", e)
            self.pool = None

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def fetch(self, sql: str, *args):
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args):
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    async def execute(self, sql: str, *args) -> str:
        if not self.pool: return ""
        async with self.pool.acquire() as conn:
            return await conn.execute(sql, *args)


db = Database()
