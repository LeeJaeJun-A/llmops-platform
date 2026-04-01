"""Tests for prompt management API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from llmops.api.middleware.auth import verify_api_key
from llmops.dependencies import get_db
from llmops.main import app

AUTH = {"Authorization": "Bearer test-key"}


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
async def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_prompt_result():
    return {
        "id": "prompt-1",
        "name": "greeting",
        "description": "A greeting prompt",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00+00:00",
        "latest_version": {
            "id": "v-1",
            "prompt_id": "prompt-1",
            "version": 1,
            "template": "Hello {{ name }}!",
            "environment": "draft",
            "variables": {"name": "World"},
            "change_note": "initial",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    }


@pytest.mark.asyncio
async def test_create_prompt(client, sample_prompt_result):
    with patch(
        "llmops.core.prompts.manager.PromptManager.create",
        new_callable=AsyncMock,
        return_value=sample_prompt_result,
    ):
        resp = await client.post(
            "/v1/prompts",
            json={
                "name": "greeting",
                "template": "Hello {{ name }}!",
                "description": "A greeting prompt",
            },
            headers=AUTH,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "greeting"


@pytest.mark.asyncio
async def test_list_prompts(client, sample_prompt_result):
    with patch(
        "llmops.core.prompts.manager.PromptManager.list_prompts",
        new_callable=AsyncMock,
        return_value=[sample_prompt_result],
    ):
        resp = await client.get("/v1/prompts", headers=AUTH)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_prompt(client):
    version_data = {
        "id": "v-1",
        "prompt_id": "prompt-1",
        "version": 1,
        "template": "Hello {{ name }}!",
        "environment": "draft",
        "variables": {"name": "World"},
        "change_note": "initial",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    with patch(
        "llmops.core.prompts.manager.PromptManager.get",
        new_callable=AsyncMock,
        return_value=version_data,
    ):
        resp = await client.get("/v1/prompts/greeting", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["version"] == 1


@pytest.mark.asyncio
async def test_get_prompt_not_found(client):
    with patch(
        "llmops.core.prompts.manager.PromptManager.get",
        new_callable=AsyncMock,
        side_effect=ValueError("Prompt not found"),
    ):
        resp = await client.get("/v1/prompts/nonexistent", headers=AUTH)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compile_prompt(client):
    version_data = {
        "id": "v-1",
        "prompt_id": "prompt-1",
        "version": 1,
        "template": "Hello {{ name }}!",
        "environment": "draft",
        "variables": {"name": "World"},
        "change_note": "",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    with patch(
        "llmops.core.prompts.manager.PromptManager.get",
        new_callable=AsyncMock,
        return_value=version_data,
    ):
        resp = await client.post(
            "/v1/prompts/greeting/compile",
            json={"variables": {"name": "Alice"}},
            headers=AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rendered"] == "Hello Alice!"
        assert data["version"] == 1


@pytest.mark.asyncio
async def test_promote_prompt(client):
    result = {
        "id": "v-1",
        "prompt_id": "prompt-1",
        "version": 1,
        "template": "Hello {{ name }}!",
        "environment": "production",
        "variables": {"name": "World"},
        "change_note": "",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    with patch(
        "llmops.core.prompts.manager.PromptManager.promote",
        new_callable=AsyncMock,
        return_value=result,
    ):
        resp = await client.post(
            "/v1/prompts/greeting/promote",
            json={"version": 1, "target_env": "production"},
            headers=AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["environment"] == "production"
