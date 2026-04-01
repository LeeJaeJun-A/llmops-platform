"""Tests for LangfuseCostTracker."""

from unittest.mock import MagicMock, patch

import pytest

from llmops.core.gateway.langfuse_cost_tracker import LangfuseCostTracker


def _make_observation(
    *,
    model: str = "claude-sonnet-4-20250514",
    total_cost: float = 0.001,
    input_tokens: int = 100,
    output_tokens: int = 50,
    service_name: str = "test-svc",
):
    obs = MagicMock()
    obs.provided_model_name = model
    obs.total_cost = total_cost
    obs.usage_details = {"input": input_tokens, "output": output_tokens}
    obs.metadata = {"service_name": service_name}
    return obs


@pytest.fixture
def tracker():
    with patch(
        "llmops.core.gateway.langfuse_cost_tracker.LangfuseAPI"
    ):
        t = LangfuseCostTracker()
        return t


@pytest.mark.asyncio
async def test_record_is_noop(tracker):
    cost = await tracker.record(
        service_name="svc",
        model="claude-sonnet-4-20250514",
        input_tokens=100,
        output_tokens=50,
    )
    assert cost == 0.0


@pytest.mark.asyncio
async def test_get_summary_aggregates(tracker):
    obs1 = _make_observation(
        model="claude-sonnet-4-20250514",
        total_cost=0.003,
        input_tokens=1000,
        output_tokens=500,
    )
    obs2 = _make_observation(
        model="gemini-2.0-flash",
        total_cost=0.0001,
        input_tokens=500,
        output_tokens=200,
    )

    response = MagicMock()
    response.data = [obs1, obs2]
    response.meta = MagicMock()
    response.meta.next_cursor = None
    tracker._api.observations.get_many = MagicMock(return_value=response)

    result = await tracker.get_summary()

    assert "services" in result
    svc_data = result["services"]["test-svc"]
    assert svc_data["total_requests"] == 2
    assert svc_data["total_input_tokens"] == 1500
    assert svc_data["total_output_tokens"] == 700
    assert svc_data["total_cost"] == round(0.003 + 0.0001, 8)
    assert "claude-sonnet-4-20250514" in svc_data["models"]
    assert "gemini-2.0-flash" in svc_data["models"]


@pytest.mark.asyncio
async def test_get_summary_filters_by_service(tracker):
    obs1 = _make_observation(service_name="svc-a", total_cost=0.01)
    obs2 = _make_observation(service_name="svc-b", total_cost=0.02)

    response = MagicMock()
    response.data = [obs1, obs2]
    response.meta = MagicMock()
    response.meta.next_cursor = None
    tracker._api.observations.get_many = MagicMock(return_value=response)

    result = await tracker.get_summary(service_name="svc-a")

    assert result["service"] == "svc-a"
    assert result["total_requests"] == 1
    assert result["total_cost"] == 0.01


@pytest.mark.asyncio
async def test_get_summary_empty(tracker):
    response = MagicMock()
    response.data = []
    response.meta = MagicMock()
    response.meta.next_cursor = None
    tracker._api.observations.get_many = MagicMock(return_value=response)

    result = await tracker.get_summary()

    assert result == {"services": {}}


@pytest.mark.asyncio
async def test_get_summary_handles_error(tracker):
    tracker._api.observations.get_many = MagicMock(
        side_effect=Exception("connection failed"),
    )

    result = await tracker.get_summary()

    assert "error" in result


@pytest.mark.asyncio
async def test_get_summary_paginates(tracker):
    obs1 = _make_observation(total_cost=0.01)
    obs2 = _make_observation(total_cost=0.02)

    page1 = MagicMock()
    page1.data = [obs1]
    page1.meta = MagicMock()
    page1.meta.next_cursor = "cursor-1"

    page2 = MagicMock()
    page2.data = [obs2]
    page2.meta = MagicMock()
    page2.meta.next_cursor = None

    tracker._api.observations.get_many = MagicMock(
        side_effect=[page1, page2],
    )

    result = await tracker.get_summary()

    svc_data = result["services"]["test-svc"]
    assert svc_data["total_requests"] == 2
    assert svc_data["total_cost"] == 0.03
