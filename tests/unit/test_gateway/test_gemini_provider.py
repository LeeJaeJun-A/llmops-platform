"""Tests for Gemini provider implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llmops.core.gateway.schemas import ChatRequest, Message, Role


@pytest.fixture
def chat_request():
    return ChatRequest(
        model="gemini-2.5-flash",
        messages=[
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hello"),
        ],
        temperature=0.5,
        max_tokens=100,
    )


@pytest.mark.asyncio
async def test_chat_returns_response(chat_request):
    with patch("llmops.core.gateway.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.text = "Hello from Gemini!"

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        mock_candidate.finish_reason = "STOP"

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.response_id = "gemini-123"
        mock_response.usage_metadata.prompt_token_count = 8
        mock_response.usage_metadata.candidates_token_count = 4

        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        from llmops.core.gateway.gemini import GeminiProvider

        provider = GeminiProvider()
        response = await provider.chat(chat_request)

        assert response.id == "gemini-123"
        assert response.content == "Hello from Gemini!"
        assert response.usage.input_tokens == 8
        assert response.usage.output_tokens == 4


@pytest.mark.asyncio
async def test_chat_empty_response(chat_request):
    with patch("llmops.core.gateway.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_candidate = MagicMock()
        mock_candidate.content = None
        mock_candidate.finish_reason = None

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.response_id = None
        mock_response.usage_metadata = None

        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        from llmops.core.gateway.gemini import GeminiProvider

        provider = GeminiProvider()
        response = await provider.chat(chat_request)

        assert response.content == ""
        assert response.usage.input_tokens == 0


@pytest.mark.asyncio
async def test_chat_safety_filter(chat_request):
    with patch("llmops.core.gateway.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.text = ""

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        mock_candidate.finish_reason = "SAFETY"

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.response_id = "gemini-safety"
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 0

        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        from llmops.core.gateway.gemini import GeminiProvider

        provider = GeminiProvider()
        response = await provider.chat(chat_request)

        assert response.choices[0].finish_reason == "content_filter"


def test_supports_model():
    with patch("llmops.core.gateway.gemini.genai"):
        from llmops.core.gateway.gemini import GeminiProvider

        provider = GeminiProvider()
        assert provider.supports_model("gemini-2.5-flash") is True
        assert provider.supports_model("gemini-custom") is True
        assert provider.supports_model("claude-sonnet-4-20250514") is False
        assert provider.provider_name == "gemini"


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks(chat_request):
    with patch("llmops.core.gateway.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        # First chunk: content
        mock_part1 = MagicMock()
        mock_part1.text = "Hello"
        mock_content1 = MagicMock()
        mock_content1.parts = [mock_part1]
        chunk1 = MagicMock()
        chunk1.candidates = [MagicMock()]
        chunk1.candidates[0].content = mock_content1
        chunk1.candidates[0].finish_reason = None
        chunk1.usage_metadata = None

        # Second chunk: finish
        mock_part2 = MagicMock()
        mock_part2.text = " world"
        mock_content2 = MagicMock()
        mock_content2.parts = [mock_part2]
        chunk2 = MagicMock()
        chunk2.candidates = [MagicMock()]
        chunk2.candidates[0].content = mock_content2
        chunk2.candidates[0].finish_reason = "STOP"
        chunk2.usage_metadata = MagicMock()
        chunk2.usage_metadata.prompt_token_count = 5
        chunk2.usage_metadata.candidates_token_count = 3

        async def mock_stream():
            for c in [chunk1, chunk2]:
                yield c

        mock_client.aio.models.generate_content_stream = AsyncMock(return_value=mock_stream())

        from llmops.core.gateway.gemini import GeminiProvider

        provider = GeminiProvider()
        chunks = []
        async for chunk in provider.chat_stream(chat_request):
            chunks.append(chunk)

        assert len(chunks) >= 2
        assert chunks[0].delta_content == "Hello"
