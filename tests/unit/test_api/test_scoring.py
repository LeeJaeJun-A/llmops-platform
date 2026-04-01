"""Tests for scoring API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from llmops.api.middleware.auth import verify_api_key
from llmops.api.middleware.rate_limit import rate_limit_dependency
from llmops.dependencies import get_db, get_observability_backend
from llmops.main import app

AUTH = {"Authorization": "Bearer test-key"}


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_observability():
    obs = AsyncMock()
    obs.score = AsyncMock()
    obs.flush = AsyncMock()
    return obs


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
async def test_list_strategies(client):
    resp = await client.get("/v1/scoring/strategies", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data
    assert isinstance(data["strategies"], list)


@pytest.mark.asyncio
async def test_create_pipeline(client, mock_db):
    pipeline_id = uuid.uuid4()
    now = datetime.now(UTC)

    async def fake_refresh(obj):
        obj.id = pipeline_id
        obj.created_at = now
        obj.is_active = True

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    resp = await client.post(
        "/v1/scoring/pipelines",
        json={
            "name": "test-pipeline",
            "description": "A test pipeline",
            "scorers": [{"strategy": "rule_based", "weight": 1.0, "config": {}}],
        },
        headers=AUTH,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-pipeline"
    assert mock_db.add.called


@pytest.mark.asyncio
async def test_create_pipeline_unknown_strategy(client):
    resp = await client.post(
        "/v1/scoring/pipelines",
        json={
            "name": "bad-pipeline",
            "scorers": [{"strategy": "nonexistent_strategy"}],
        },
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "Unknown strategy" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_pipelines_empty(client, mock_db):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)

    resp = await client.get("/v1/scoring/pipelines", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["pipelines"] == []


@pytest.mark.asyncio
async def test_get_pipeline_not_found(client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    resp = await client.get(f"/v1/scoring/pipelines/{uuid.uuid4()}", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_results_empty(client, mock_db):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)

    resp = await client.get("/v1/scoring/results/trace-123", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == "trace-123"
    assert data["results"] == []
