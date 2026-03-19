import os
from typing import Optional
import asyncpg

_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "radius"),
            user=os.getenv("DB_USER", "radius"),
            password=os.getenv("DB_PASSWORD", "radius"),
            min_size=2,
            max_size=10,
        )
    return _pool
