"""可选 Redis 缓存，未配置或连接失败时自动降级到 SQLite。"""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_redis = None
_redis_initialized = False
_process_locks: dict[str, asyncio.Lock] = {}
_process_locks_guard = asyncio.Lock()


class CacheLockTimeout(Exception):
    """等待分布式缓存锁超时。"""


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


async def cache_set_json(key: str, value: dict, ttl: Optional[int] = None) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        payload = json.dumps(value, ensure_ascii=False)
        if ttl is None:
            await client.set(key, payload)
        else:
            await client.set(key, payload, ex=ttl)
    except Exception:
        logger.warning("Redis cache write failed", exc_info=True)


async def cache_delete_json(key: str) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception:
        logger.warning("Redis cache delete failed", exc_info=True)


async def _acquire_redis_lock(key: str, ttl: int):
    """返回 token 表示获得锁，None 表示锁被占用，"unavailable" 表示 Redis 不可用。"""
    client = _get_redis()
    if client is None:
        return "unavailable"
    token = uuid.uuid4().hex
    try:
        acquired = await client.set(key, token, nx=True, ex=ttl)
        return token if acquired else None
    except Exception:
        logger.warning("Redis lock acquire failed", exc_info=True)
        return "unavailable"


async def _release_redis_lock(key: str, token: str) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        await client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1,
            key,
            token,
        )
    except Exception:
        logger.warning("Redis lock release failed", exc_info=True)


@asynccontextmanager
async def resource_lock(name: str, ttl: int = 180, wait_timeout: float = 90.0):
    """带 Redis 分布式锁的异步互斥，Redis 不可用时降级为进程内锁。"""
    key = f"dota2:lock:{name}"
    async with _process_locks_guard:
        local_lock = _process_locks.setdefault(key, asyncio.Lock())

    first = await _acquire_redis_lock(key, ttl)

    if first not in (None, "unavailable"):
        token = first
        try:
            async with local_lock:
                yield
        finally:
            await _release_redis_lock(key, token)
        return

    if first == "unavailable":
        async with local_lock:
            yield
        return

    loop = asyncio.get_event_loop()
    deadline = loop.time() + wait_timeout
    while True:
        state = await _acquire_redis_lock(key, ttl)
        if state and state != "unavailable":
            token = state
            try:
                async with local_lock:
                    yield
            finally:
                await _release_redis_lock(key, token)
            return
        if state == "unavailable":
            async with local_lock:
                yield
            return
        if loop.time() >= deadline:
            raise CacheLockTimeout(f"锁等待超时: {name}")
        await asyncio.sleep(0.2)
