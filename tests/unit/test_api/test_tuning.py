"""Tests for tuning/experiment API endpoints."""

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
def sample_experiment():
    return {
        "id": "exp-1",
        "name": "test-experiment",
        "description": "A/B test",
        "status": "draft",
        "allocation_strategy": "ab_test",
        "parameter_space": {"parameters": []},
        "variants": [],
        "scoring_pipeline_id": None,
        "traffic_percentage": 100.0,
        "winner_variant_id": None,
        "concluded_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_create_experiment(client, sample_experiment):
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.create",
        new_callable=AsyncMock,
        return_value=sample_experiment,
    ):
        resp = await client.post(
            "/v1/tuning/experiments",
            json={
                "name": "test-experiment",
                "description": "A/B test",
                "parameter_space": {"parameters": []},
                "variants": [
                    {"variant_id": "control", "values": {"temperature": 0.7}},
                    {"variant_id": "variant-a", "values": {"temperature": 1.0}},
                ],
            },
            headers=AUTH,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "test-experiment"


@pytest.mark.asyncio
async def test_list_experiments(client, sample_experiment):
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.list_experiments",
        new_callable=AsyncMock,
        return_value=[sample_experiment],
    ):
        resp = await client.get("/v1/tuning/experiments", headers=AUTH)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_experiment(client, sample_experiment):
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.get",
        new_callable=AsyncMock,
        return_value=sample_experiment,
    ):
        resp = await client.get("/v1/tuning/experiments/exp-1", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["id"] == "exp-1"


@pytest.mark.asyncio
async def test_get_experiment_not_found(client):
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.get",
        new_callable=AsyncMock,
        side_effect=ValueError("Experiment not found"),
    ):
        resp = await client.get("/v1/tuning/experiments/missing", headers=AUTH)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_experiment(client, sample_experiment):
    running = {**sample_experiment, "status": "running"}
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.start",
        new_callable=AsyncMock,
        return_value=running,
    ):
        resp = await client.post("/v1/tuning/experiments/exp-1/start", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_conclude_experiment(client, sample_experiment):
    concluded = {
        **sample_experiment,
        "status": "concluded",
        "winner_variant_id": "control",
        "concluded_at": "2026-01-02T00:00:00+00:00",
    }
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.conclude",
        new_callable=AsyncMock,
        return_value=concluded,
    ):
        resp = await client.post(
            "/v1/tuning/experiments/exp-1/conclude",
            json={"winner_variant_id": "control"},
            headers=AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["winner_variant_id"] == "control"


@pytest.mark.asyncio
async def test_get_results(client):
    results = {
        "id": "exp-1",
        "name": "test",
        "status": "running",
        "total_trials": 10,
        "results": [
            {
                "variant_id": "control",
                "parameters": {"temperature": 0.7},
                "sample_count": 5,
                "avg_score": 0.85,
                "min_score": 0.7,
                "max_score": 1.0,
            },
        ],
    }
    with patch(
        "llmops.core.tuning.experiment.ExperimentRunner.get_results",
        new_callable=AsyncMock,
        return_value=results,
    ):
        resp = await client.get("/v1/tuning/experiments/exp-1/results", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trials"] == 10
        assert len(data["results"]) == 1
