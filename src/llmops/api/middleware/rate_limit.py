"""Redis-backed token bucket rate limiting middleware."""

import logging
import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request

from llmops.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter backed by Redis."""

    def __init__(self, redis_url: str, requests_per_minute: int) -> None:
        self._redis_url = redis_url
        self._rpm = requests_per_minute

    async def check(self, key: str) -> None:
        """Check if the key has exceeded the rate limit. Raises 429 if so."""
        if self._rpm <= 0:
            return

        client = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            redis_key = f"llmops:ratelimit:{key}"
            now = time.time()
            window_start = now - 60  # 1-minute sliding window

            pipe = client.pipeline()
            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)
            # Count requests in current window
            pipe.zcard(redis_key)
            # Add current request
            pipe.zadd(redis_key, {str(now): now})
            # Set expiry on the key
            pipe.expire(redis_key, 120)
            results = await pipe.execute()

            request_count = results[1]

            if request_count >= self._rpm:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {self._rpm} requests/minute",
                    headers={"Retry-After": "60"},
                )
        finally:
            await client.aclose()


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(
            redis_url=settings.redis_url,
            requests_per_minute=settings.rate_limit_requests_per_minute,
        )
    return _limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter instance (for testing)."""
    global _limiter
    _limiter = None


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency for rate limiting based on service name or IP."""
    limiter = get_rate_limiter()
    service_name = request.headers.get("X-Service-Name", "")
    key = service_name or (request.client.host if request.client else "unknown")
    try:
        await limiter.check(key)
    except HTTPException:
        raise
    except Exception:
        logger.warning("Rate limiter unavailable (Redis down?), allowing request")
        return
