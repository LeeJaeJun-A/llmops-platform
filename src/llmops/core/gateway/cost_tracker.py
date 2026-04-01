"""Cost tracker — ABC + Redis-backed implementation."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from llmops.config import settings

# Approximate cost per 1M tokens (input/output) — update as pricing changes
COST_PER_MILLION: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-20250506": {"input": 0.80, "output": 4.0},
    # Gemini
    "gemini-2.5-pro-preview-05-06": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash-preview-05-20": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    pricing = COST_PER_MILLION.get(model)
    if not pricing:
        pricing = {"input": 1.0, "output": 3.0}

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)


class CostTracker(ABC):
    """Abstract base class for cost tracking."""

    @abstractmethod
    async def record(
        self,
        *,
        service_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record token usage and return estimated cost."""

    @abstractmethod
    async def get_summary(
        self,
        service_name: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get usage summary, optionally filtered by service and time range."""


class RedisCostTracker(CostTracker):
    """Redis-backed cost and usage tracking per service/model."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url

    async def record(
        self,
        *,
        service_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        cost = estimate_cost(model, input_tokens, output_tokens)

        client = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            pipe = client.pipeline()

            svc_key = f"llmops:usage:{service_name}"
            pipe.hincrbyfloat(svc_key, "total_cost", cost)
            pipe.hincrby(svc_key, "total_input_tokens", input_tokens)
            pipe.hincrby(svc_key, "total_output_tokens", output_tokens)
            pipe.hincrby(svc_key, "total_requests", 1)

            model_key = f"llmops:usage:{service_name}:{model}"
            pipe.hincrbyfloat(model_key, "cost", cost)
            pipe.hincrby(model_key, "input_tokens", input_tokens)
            pipe.hincrby(model_key, "output_tokens", output_tokens)
            pipe.hincrby(model_key, "requests", 1)

            await pipe.execute()
        finally:
            await client.aclose()

        return cost

    async def get_summary(
        self,
        service_name: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> dict[str, Any]:
        client = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            if service_name:
                return await self._get_service_summary(client, service_name)

            services: dict[str, Any] = {}
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor, match="llmops:usage:*", count=100
                )
                for key in keys:
                    parts = key.split(":")
                    if len(parts) == 3:  # llmops:usage:<service>
                        svc = parts[2]
                        if svc not in services:
                            services[svc] = await self._get_service_summary(
                                client, svc,
                            )
                if cursor == 0:
                    break

            return {"services": services}
        finally:
            await client.aclose()

    async def _get_service_summary(
        self, client: aioredis.Redis, service_name: str,
    ) -> dict[str, Any]:
        data = await client.hgetall(f"llmops:usage:{service_name}")
        return {
            "service": service_name,
            "total_cost": float(data.get("total_cost", 0)),
            "total_input_tokens": int(data.get("total_input_tokens", 0)),
            "total_output_tokens": int(data.get("total_output_tokens", 0)),
            "total_requests": int(data.get("total_requests", 0)),
        }


_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    global _tracker
    if _tracker is None:
        match settings.observability_backend.value:
            case "langfuse":
                from llmops.core.gateway.langfuse_cost_tracker import (
                    LangfuseCostTracker,
                )

                _tracker = LangfuseCostTracker()
            case _:
                _tracker = RedisCostTracker()
    return _tracker


def reset_cost_tracker() -> None:
    """Reset the global cost tracker instance (for testing)."""
    global _tracker
    _tracker = None
