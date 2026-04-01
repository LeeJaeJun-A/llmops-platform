"""Tests for Anthropic provider implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llmops.core.gateway.schemas import ChatRequest, Message, Role


@pytest.fixture
def chat_request():
    return ChatRequest(
        model="claude-sonnet-4-20250514",
        messages=[
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hello"),
        ],
        temperature=0.5,
        max_tokens=100,
    )


@pytest.fixture
def chat_request_with_stop():
    return ChatRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role=Role.USER, content="Hello")],
        stop=["END", "STOP"],
    )


@pytest.mark.asyncio
async def test_chat_returns_response(chat_request):
    with patch("llmops.core.gateway.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "Hello there!"

        mock_response = MagicMock()
        mock_response.id = "msg-123"
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.content = [mock_block]
        mock_response.stop_reason = "stop"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from llmops.core.gateway.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        response = await provider.chat(chat_request)

        assert response.id == "msg-123"
        assert response.content == "Hello there!"
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 5
        assert response.usage.total_tokens == 15
        assert response.choices[0].finish_reason == "stop"

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are helpful."
        assert call_kwargs["temperature"] == 0.5


@pytest.mark.asyncio
async def test_chat_with_stop_sequences(chat_request_with_stop):
    with patch("llmops.core.gateway.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "Response"
        mock_response = MagicMock()
        mock_response.id = "msg-456"
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.content = [mock_block]
        mock_response.stop_reason = "stop"
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 3

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from llmops.core.gateway.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        await provider.chat(chat_request_with_stop)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["stop_sequences"] == ["END", "STOP"]


def test_supports_model():
    with patch("llmops.core.gateway.anthropic.AsyncAnthropic"):
        from llmops.core.gateway.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        assert provider.supports_model("claude-sonnet-4-20250514") is True
        assert provider.supports_model("claude-custom-model") is True
        assert provider.supports_model("gemini-2.0-flash") is False
        assert provider.provider_name == "anthropic"


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks(chat_request):
    with patch("llmops.core.gateway.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        # Build mock stream events
        delta_event = MagicMock()
        delta_event.type = "content_block_delta"
        delta_event.delta.text = "Hello"

        stop_event = MagicMock()
        stop_event.type = "message_stop"

        final_snapshot = MagicMock()
        final_snapshot.stop_reason = "stop"
        final_snapshot.usage.input_tokens = 10
        final_snapshot.usage.output_tokens = 3

        mock_stream = MagicMock()
        mock_stream.current_message_snapshot = final_snapshot

        async def async_iter_events():
            for event in [delta_event, stop_event]:
                yield event

        mock_stream.__aiter__ = lambda self: async_iter_events()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        from llmops.core.gateway.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        chunks = []
        async for chunk in provider.chat_stream(chat_request):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].delta_content == "Hello"
        assert chunks[1].finish_reason == "stop"
        assert chunks[1].usage is not None
        assert chunks[1].usage.total_tokens == 13
