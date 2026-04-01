"""Tests for gateway endpoint — /v1/chat/completions."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from llmops.api.middleware.auth import verify_api_key
from llmops.api.middleware.rate_limit import rate_limit_dependency
from llmops.core.gateway.router import LLMRouter
from llmops.core.gateway.schemas import ChatResponse, Choice, Message, Role, Usage
from llmops.dependencies import get_db, get_observability_backend
from llmops.main import app


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_observability():
    obs = AsyncMock()
    obs.score = AsyncMock()
    obs.flush = AsyncMock()
    return obs


@pytest.fixture
def mock_llm_response():
    return ChatResponse(
        id="resp-1",
        model="claude-sonnet-4-20250514",
        choices=[
            Choice(
                index=0,
                message=Message(role=Role.ASSISTANT, content="Hello!"),
                finish_reason="end_turn",
            )
        ],
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
        metadata={},
    )


@pytest.fixture
async def client(mock_db, mock_observability):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_observability_backend] = lambda: mock_observability
    app.dependency_overrides[rate_limit_dependency] = lambda: None
    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_completions_success(client, mock_llm_response):
    with patch(
        "llmops.api.v1.gateway.get_llm_router"
    ) as mock_get_router:
        mock_router = AsyncMock(spec=LLMRouter)
        mock_router.chat = AsyncMock(return_value=mock_llm_response)
        mock_get_router.return_value = mock_router

        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hi"}],
            },
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "claude-sonnet-4-20250514"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["usage"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_chat_completions_invalid_temperature(client):
    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 5.0,
        },
    )
    assert resp.status_code == 422  # Pydantic validation error
