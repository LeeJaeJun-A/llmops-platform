from collections.abc import AsyncIterator

import pytest

from llmops.core.gateway.base import LLMProvider
from llmops.core.gateway.registry import ProviderRegistry
from llmops.core.gateway.schemas import ChatRequest, ChatResponse, ChatResponseChunk


class FakeProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "fake"

    def supports_model(self, model: str) -> bool:
        return model.startswith("fake-")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatResponseChunk]:
        raise NotImplementedError
        yield  # type: ignore


def test_register_and_resolve():
    registry = ProviderRegistry()
    provider = FakeProvider()
    registry.register(provider)

    resolved = registry.resolve("fake-model-v1")
    assert resolved is provider


def test_resolve_unknown_model():
    registry = ProviderRegistry()
    registry.register(FakeProvider())

    with pytest.raises(ValueError, match="No provider found"):
        registry.resolve("unknown-model")


def test_list_providers():
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    assert registry.list_providers() == ["fake"]
