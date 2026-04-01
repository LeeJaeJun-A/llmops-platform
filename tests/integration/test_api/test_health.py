"""Integration test: health endpoints against real services.

Requires: DATABASE_URL and REDIS_URL pointing to running instances.
Run with: make test-integration
"""

import pytest
from httpx import ASGITransport, AsyncClient

from llmops.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.integration
@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readyz(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["checks"]["postgresql"] == "ok"
    assert data["checks"]["redis"] == "ok"
