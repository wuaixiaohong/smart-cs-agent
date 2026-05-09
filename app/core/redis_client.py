from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import get_settings
from app.utils.logger import logger

settings = get_settings()

_redis_pool: Redis | None = None


async def get_redis() -> Redis | None:
    global _redis_pool
    if not settings.REDIS_ENABLED:
        return None
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            await _redis_pool.ping()
            logger.info("Redis 连接成功: %s", settings.REDIS_URL)
        except Exception as e:
            logger.warning("Redis 不可用，降级为内存缓存: %s", e)
            return None
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


class CacheService:
    """缓存服务：优先 Redis，降级内存字典"""

    def __init__(self) -> None:
        self._fallback: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        r = await get_redis()
        if r:
            val = await r.get(key)
            return json.loads(val) if val else None
        return self._fallback.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        r = await get_redis()
        if r:
            await r.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
            return
        self._fallback[key] = value

    async def delete(self, key: str) -> None:
        r = await get_redis()
        if r:
            await r.delete(key)
            return
        self._fallback.pop(key, None)

    async def exists(self, key: str) -> bool:
        r = await get_redis()
        if r:
            return await r.exists(key) > 0
        return key in self._fallback


cache = CacheService()
