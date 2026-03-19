import json
import os
from typing import Optional
import redis.asyncio as aioredis

_redis: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True,
        )
    return _redis

async def get_failed_attempts(username: str) -> int:
    r = await get_redis()
    count = await r.get(f"rate_limit:{username}")
    return int(count) if count else 0

async def increment_failed_attempts(username: str, window: int) -> int:
    r = await get_redis()
    key = f"rate_limit:{username}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return results[0]

async def clear_failed_attempts(username: str):
    r = await get_redis()
    await r.delete(f"rate_limit:{username}")

async def cache_session(session_id: str, data: dict):
    r = await get_redis()
    pipe = r.pipeline()
    pipe.set(f"session:{session_id}", json.dumps(data), ex=86400)
    pipe.sadd("active_sessions", session_id)
    await pipe.execute()

async def update_session(session_id: str, updates: dict):
    r = await get_redis()
    key = f"session:{session_id}"
    existing = await r.get(key)
    if existing:
        data = json.loads(existing)
        data.update(updates)
        await r.set(key, json.dumps(data), keepttl=True)

async def remove_session(session_id: str):
    r = await get_redis()
    pipe = r.pipeline()
    pipe.delete(f"session:{session_id}")
    pipe.srem("active_sessions", session_id)
    await pipe.execute()

async def get_all_sessions() -> list:
    r = await get_redis()
    ids = await r.smembers("active_sessions")
    sessions = []
    for sid in ids:
        raw = await r.get(f"session:{sid}")
        if raw:
            sessions.append(json.loads(raw))
    return sessions
