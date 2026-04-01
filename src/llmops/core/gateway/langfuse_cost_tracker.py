"""Langfuse-backed cost tracker — uses Langfuse as source of truth for costs."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from langfuse.api.client import LangfuseAPI

from llmops.config import settings
from llmops.core.gateway.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class LangfuseCostTracker(CostTracker):
    """Queries Langfuse observations API for cost and usage data.

    Langfuse calculates cost server-side based on model pricing × token usage.
    record() is a no-op since Langfuse tracks costs automatically via
    log_generation() in the observability backend.
    """

    def __init__(self) -> None:
        self._api = LangfuseAPI(
            base_url=settings.langfuse_host,
            username=settings.langfuse_public_key,
            password=settings.langfuse_secret_key,
        )

    async def record(
        self,
        *,
        service_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        # No-op: Langfuse records costs automatically via log_generation
        return 0.0

    async def get_summary(
        self,
        service_name: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Query Langfuse observations API and aggregate cost/usage."""
        try:
            return await self._query_langfuse(
                service_name=service_name,
                from_time=from_time,
                to_time=to_time,
            )
        except Exception:
            logger.exception("Failed to query Langfuse for cost data")
            return {"services": {}, "error": "Langfuse query failed"}

    async def _query_langfuse(
        self,
        service_name: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> dict[str, Any]:
        all_observations = []
        cursor = None

        while True:
            response = self._api.observations.get_many(
                type="GENERATION",
                from_start_time=from_time,
                to_start_time=to_time,
                limit=100,
                cursor=cursor,
            )

            all_observations.extend(response.data)

            if not response.meta or not response.meta.next_cursor:
                break
            cursor = response.meta.next_cursor

        return self._aggregate(all_observations, service_name)

    def _aggregate(
        self,
        observations: list,
        service_name: str | None,
    ) -> dict[str, Any]:
        """Aggregate observations into per-service/model summaries."""
        services: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_cost": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_requests": 0,
                "models": defaultdict(
                    lambda: {
                        "cost": 0.0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "requests": 0,
                    },
                ),
            },
        )

        for obs in observations:
            # Extract service name from trace metadata
            svc = "unknown"
            if obs.metadata and isinstance(obs.metadata, dict):
                svc = obs.metadata.get("service_name", "unknown")

            if service_name and svc != service_name:
                continue

            model = obs.provided_model_name or "unknown"
            cost = obs.total_cost or 0.0
            usage = obs.usage_details or {}
            input_t = usage.get("input", 0) or 0
            output_t = usage.get("output", 0) or 0

            svc_data = services[svc]
            svc_data["total_cost"] += cost
            svc_data["total_input_tokens"] += input_t
            svc_data["total_output_tokens"] += output_t
            svc_data["total_requests"] += 1

            model_data = svc_data["models"][model]
            model_data["cost"] += cost
            model_data["input_tokens"] += input_t
            model_data["output_tokens"] += output_t
            model_data["requests"] += 1

        if service_name:
            svc_data = services.get(service_name, {})
            if svc_data:
                return {
                    "service": service_name,
                    "total_cost": round(svc_data["total_cost"], 8),
                    "total_input_tokens": svc_data["total_input_tokens"],
                    "total_output_tokens": svc_data["total_output_tokens"],
                    "total_requests": svc_data["total_requests"],
                    "models": dict(svc_data["models"]),
                }
            return {
                "service": service_name,
                "total_cost": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_requests": 0,
            }

        result = {}
        for svc, data in services.items():
            result[svc] = {
                "service": svc,
                "total_cost": round(data["total_cost"], 8),
                "total_input_tokens": data["total_input_tokens"],
                "total_output_tokens": data["total_output_tokens"],
                "total_requests": data["total_requests"],
                "models": dict(data["models"]),
            }
        return {"services": result}
