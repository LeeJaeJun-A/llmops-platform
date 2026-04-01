from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from llmops.config import settings
from llmops.core.observability.base import ObservabilityBackend, Trace


class LangfuseBackend(ObservabilityBackend):
    """Langfuse v4 observability backend implementation."""

    def __init__(self) -> None:
        from langfuse import Langfuse

        self._client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        *,
        input: Any = None,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[Trace]:
        trace_id = self._client.create_trace_id()
        span = self._client.start_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            as_type="span",
            input=input,
            metadata={
                "user_id": user_id,
                "session_id": session_id,
                **(metadata or {}),
            },
        )
        try:
            yield Trace(
                trace_id=trace_id,
                name=name,
                metadata={"langfuse_span": span, **(metadata or {})},
            )
        finally:
            span.end()
            self._client.flush()

    async def log_generation(
        self,
        trace_id: str,
        *,
        name: str,
        model: str,
        input: Any,
        output: Any,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        usage_details = None
        if usage:
            usage_details = {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "total": usage.get("total_tokens", 0),
            }

        gen = self._client.start_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            as_type="generation",
            model=model,
            input=input,
            output=output,
            usage_details=usage_details,
            metadata=metadata or {},
        )
        gen.end()

    async def score(
        self,
        trace_id: str,
        name: str,
        value: float | str | bool,
        *,
        observation_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        score_value = float(value) if isinstance(value, bool) else value
        self._client.create_score(
            trace_id=trace_id,
            observation_id=observation_id,
            name=name,
            value=score_value,
            comment=comment,
        )

    async def flush(self) -> None:
        self._client.flush()
