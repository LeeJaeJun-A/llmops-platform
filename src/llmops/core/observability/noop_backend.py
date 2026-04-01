import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from llmops.core.observability.base import ObservabilityBackend, Trace


class NoopBackend(ObservabilityBackend):
    """No-op observability backend for testing and development."""

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
        yield Trace(trace_id=str(uuid.uuid4()), name=name, metadata=metadata or {})

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
        pass

    async def score(
        self,
        trace_id: str,
        name: str,
        value: float | str | bool,
        *,
        observation_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        pass

    async def flush(self) -> None:
        pass
