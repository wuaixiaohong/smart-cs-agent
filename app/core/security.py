from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable

from fastapi import Request, HTTPException

from app.core.config import get_settings
from app.core.redis_client import get_redis

settings = get_settings()


class RateLimiter:
    """基于 Redis 的滑动窗口限流"""

    @staticmethod
    async def check(request: Request, limit: int | None = None) -> None:
        if limit is None:
            limit = settings.RATE_LIMIT_PER_MINUTE
        r = await get_redis()
        if r is None:
            return  # Redis 不可用时跳过限流

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        current = await r.get(key)

        if current is None:
            await r.setex(key, 60, 1)
        elif int(current) >= limit:
            raise HTTPException(status_code=429, detail="请求频率过高，请稍后再试")
        else:
            await r.incr(key)
