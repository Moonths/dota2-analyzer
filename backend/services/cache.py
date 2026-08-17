"""可选 Redis 缓存，未配置或连接失败时自动降级到 SQLite。"""
import json
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_redis = None
_redis_initialized = False


def _get_redis():
    global _redis, _redis_initialized
    if _redis_initialized:
        return _redis
    _redis_initialized = True
    if not settings.redis_url:
        return None
    try:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        logger.warning("Redis cache disabled: %s", exc)
        _redis = None
    return _redis


async def cache_get_json(key: str) -> Optional[dict]:
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def cache_set_json(key: str, value: dict, ttl: int = 30 * 24 * 3600) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception:
        logger.warning("Redis cache write failed", exc_info=True)
