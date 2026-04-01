from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Trace:
    """Represents an active trace context."""

    trace_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ObservabilityBackend(ABC):
    """Pluggable observability backend interface.

    Langfuse is one implementation. Can be swapped for OpenTelemetry, Datadog, or noop.
    """

    @abstractmethod
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
        """Start a trace context. Yields a Trace object for nested observations."""
        yield  # type: ignore[misc]

    @abstractmethod
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
        """Log an LLM generation (call) within a trace."""
        ...

    @abstractmethod
    async def score(
        self,
        trace_id: str,
        name: str,
        value: float | str | bool,
        *,
        observation_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Submit a score for a trace or observation."""
        ...

    @abstractmethod
    async def flush(self) -> None:
        """Flush any buffered data to the backend."""
        ...
