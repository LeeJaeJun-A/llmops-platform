"""Tests for LLM router with observability."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmops.core.gateway.schemas import (
    ChatRequest,
    ChatResponse,
    ChatResponseChunk,
    Choice,
    Message,
    Role,
    Usage,
)


@pytest.fixture
def chat_request():
    return ChatRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role=Role.USER, content="Hello")],
    )


@pytest.fixture
def chat_response():
    return ChatResponse(
        id="resp-1",
        model="claude-sonnet-4-20250514",
        choices=[
            Choice(
                index=0,
                message=Message(role=Role.ASSISTANT, content="Hi!"),
                finish_reason="stop",
            )
        ],
        usage=Usage(input_tokens=5, output_tokens=3, total_tokens=8),
    )


@pytest.fixture
def mock_provider(chat_response):
    provider = AsyncMock()
    provider.provider_name = "anthropic"
    provider.chat = AsyncMock(return_value=chat_response)
    return provider


@pytest.fixture
def mock_observability():
    obs = AsyncMock()
    # Make trace a proper async context manager
    trace_ctx = AsyncMock()
    trace_ctx.__aenter__ = AsyncMock(
        return_value=MagicMock(trace_id="trace-1", name="test", metadata={})
    )
    trace_ctx.__aexit__ = AsyncMock(return_value=False)
    obs.trace = MagicMock(return_value=trace_ctx)
    return obs


@pytest.fixture
def mock_registry(mock_provider):
    registry = MagicMock()
    registry.resolve.return_value = mock_provider
    return registry


@pytest.mark.asyncio
async def test_chat_routes_to_provider(
    chat_request, mock_registry, mock_observability, mock_provider,
):
    from llmops.core.gateway.router import LLMRouter

    cost_tracker = AsyncMock()
    cost_tracker.record = AsyncMock(return_value=0.001)
    router = LLMRouter(mock_registry, mock_observability, cost_tracker)

    response = await router.chat(chat_request, service_name="test-svc")

    assert response.content == "Hi!"
    assert response.metadata["trace_id"] == "trace-1"
    mock_provider.chat.assert_called_once_with(chat_request)
    mock_observability.log_generation.assert_called_once()
    cost_tracker.record.assert_called_once()


@pytest.mark.asyncio
async def test_chat_stream_collects_content(chat_request, mock_registry, mock_observability):
    from llmops.core.gateway.router import LLMRouter

    chunks = [
        ChatResponseChunk(id="r-1", model="test", delta_content="Hello"),
        ChatResponseChunk(id="r-1", model="test", delta_content=" world"),
        ChatResponseChunk(
            id="r-1", model="test", finish_reason="stop",
            usage=Usage(input_tokens=5, output_tokens=4, total_tokens=9),
        ),
    ]

    async def mock_stream(request):
        for chunk in chunks:
            yield chunk

    mock_registry.resolve.return_value.chat_stream = mock_stream

    cost_tracker = AsyncMock()
    cost_tracker.record = AsyncMock(return_value=0.001)
    router = LLMRouter(mock_registry, mock_observability, cost_tracker)

    result_chunks = []
    async for chunk in router.chat_stream(chat_request, service_name="test"):
        result_chunks.append(chunk)

    assert len(result_chunks) == 3
    assert result_chunks[0].delta_content == "Hello"
    assert result_chunks[2].finish_reason == "stop"
    cost_tracker.record.assert_called_once()
    mock_observability.log_generation.assert_called_once()
