"""Tests for admin endpoints (healthz, readyz, usage)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from llmops.api.middleware.auth import verify_api_key
from llmops.dependencies import get_db, get_redis
from llmops.main import app


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    return session


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.ping = AsyncMock(return_value=True)
    return r


@pytest.fixture
async def client(mock_db, mock_redis):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_all_ok(client, mock_db, mock_redis):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["checks"]["postgresql"] == "ok"
    assert data["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_readyz_db_down(client, mock_db):
    mock_db.execute.side_effect = Exception("connection refused")
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert "error" in data["checks"]["postgresql"]


@pytest.mark.asyncio
async def test_readyz_redis_down(client, mock_redis):
    mock_redis.ping.side_effect = Exception("connection refused")
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert "error" in data["checks"]["redis"]


@pytest.mark.asyncio
async def test_usage_summary(client):
    with patch(
        "llmops.api.v1.admin.get_cost_tracker"
    ) as mock_tracker_fn:
        tracker = AsyncMock()
        tracker.get_summary = AsyncMock(
            return_value={"total_cost": 0.0, "total_tokens": 0}
        )
        mock_tracker_fn.return_value = tracker

        resp = await client.get(
            "/v1/usage/summary",
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
