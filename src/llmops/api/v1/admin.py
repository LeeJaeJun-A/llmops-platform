from datetime import datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.config import settings
from llmops.core.gateway.cost_tracker import get_cost_tracker
from llmops.dependencies import get_db, get_redis

router = APIRouter(tags=["admin"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe — is the process running."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict[str, object]:
    """Readiness probe — are dependencies reachable."""
    checks: dict[str, object] = {}

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception as e:
        checks["postgresql"] = f"error: {e}"

    # Redis
    try:
        await redis.ping()  # type: ignore[misc]
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Langfuse
    if settings.observability_backend.value == "langfuse":
        checks["langfuse"] = "configured"

    all_ok = all(v == "ok" or v == "configured" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}


@router.get("/v1/usage/summary")
async def usage_summary(
    service: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> dict:
    """Get cost and token usage summary."""
    tracker = get_cost_tracker()
    return await tracker.get_summary(
        service_name=service,
        from_time=from_time,
        to_time=to_time,
    )
