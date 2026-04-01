from collections.abc import AsyncGenerator
from functools import lru_cache

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.config import Settings, settings
from llmops.core.observability.base import ObservabilityBackend
from llmops.db.session import async_session_factory


@lru_cache
def get_settings() -> Settings:
    return settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def get_observability_backend() -> ObservabilityBackend:
    from llmops.core.observability.langfuse_backend import LangfuseBackend
    from llmops.core.observability.noop_backend import NoopBackend

    match settings.observability_backend.value:
        case "langfuse":
            return LangfuseBackend()
        case "noop":
            return NoopBackend()
        case _:
            return NoopBackend()
