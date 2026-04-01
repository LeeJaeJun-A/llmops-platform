"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from llmops.core.gateway.schemas import ChatRequest, ChatResponse, ChatResponseChunk


class LLMProvider(ABC):
    """Abstract base for all LLM providers.

    Each provider translates between the unified ChatRequest/ChatResponse
    format and the provider's native API.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider (e.g., 'anthropic', 'gemini')."""
        ...

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Return True if this provider can handle the given model name."""
        ...

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming completion."""
        ...

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatResponseChunk]:
        """Streaming completion. Yields response chunks."""
        ...
