import json
import hashlib
from typing import Optional
from app.core.config import get_settings

_redis_client = None


async def get_redis():
    global _redis_client
    settings = get_settings()
    try:
        import redis.asyncio as aioredis
        if _redis_client is None:
            _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception:
        return None


async def cache_get(key: str) -> Optional[dict]:
    r = await get_redis()
    if r is None:
        return None
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def cache_set(key: str, data: dict, ttl: int = 86400):
    r = await get_redis()
    if r is None:
        return
    await r.set(key, json.dumps(data, default=str), ex=ttl)


async def cache_get_places(query: str) -> Optional[dict]:
    r = await get_redis()
    if r is None:
        return None
    key = f"places:{hashlib.md5(query.encode()).hexdigest()}"
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def cache_set_places(query: str, data: dict, ttl: int = 604800):
    r = await get_redis()
    if r is None:
        return
    key = f"places:{hashlib.md5(query.encode()).hexdigest()}"
    await r.set(key, json.dumps(data, default=str), ex=ttl)
