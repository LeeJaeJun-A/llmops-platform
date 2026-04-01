"""Tests for Langfuse observability backend."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_langfuse():
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_client.create_trace_id.return_value = "trace-abc"
    mock_span = MagicMock()
    mock_client.start_observation.return_value = mock_span
    mock_module.Langfuse.return_value = mock_client

    with patch.dict(sys.modules, {"langfuse": mock_module}):
        # Force reimport so the patched module is used
        if "llmops.core.observability.langfuse_backend" in sys.modules:
            del sys.modules["llmops.core.observability.langfuse_backend"]
        yield mock_client


@pytest.mark.asyncio
async def test_trace_creates_span_and_flushes(mock_langfuse):
    from llmops.core.observability.langfuse_backend import LangfuseBackend

    backend = LangfuseBackend()

    async with backend.trace("my-trace", input="hello") as trace:
        assert trace.trace_id == "trace-abc"
        assert trace.name == "my-trace"

    mock_langfuse.start_observation.assert_called_once()
    call_kwargs = mock_langfuse.start_observation.call_args[1]
    assert call_kwargs["name"] == "my-trace"
    assert call_kwargs["as_type"] == "span"
    mock_langfuse.flush.assert_called()


@pytest.mark.asyncio
async def test_log_generation(mock_langfuse):
    from llmops.core.observability.langfuse_backend import LangfuseBackend

    backend = LangfuseBackend()
    await backend.log_generation(
        trace_id="trace-1",
        name="gen-1",
        model="claude-sonnet-4-20250514",
        input="prompt",
        output="response",
        usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )

    call_kwargs = mock_langfuse.start_observation.call_args[1]
    assert call_kwargs["as_type"] == "generation"
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs["usage_details"]["input"] == 10
    assert call_kwargs["usage_details"]["output"] == 5


@pytest.mark.asyncio
async def test_log_generation_no_usage(mock_langfuse):
    from llmops.core.observability.langfuse_backend import LangfuseBackend

    backend = LangfuseBackend()
    await backend.log_generation(
        trace_id="trace-1",
        name="gen-1",
        model="test",
        input="in",
        output="out",
        usage=None,
    )

    call_kwargs = mock_langfuse.start_observation.call_args[1]
    assert call_kwargs["usage_details"] is None


@pytest.mark.asyncio
async def test_score_float(mock_langfuse):
    from llmops.core.observability.langfuse_backend import LangfuseBackend

    backend = LangfuseBackend()
    await backend.score(
        trace_id="trace-1",
        name="accuracy",
        value=0.95,
        comment="Good result",
    )

    mock_langfuse.create_score.assert_called_once_with(
        trace_id="trace-1",
        observation_id=None,
        name="accuracy",
        value=0.95,
        comment="Good result",
    )


@pytest.mark.asyncio
async def test_score_bool_converted_to_float(mock_langfuse):
    from llmops.core.observability.langfuse_backend import LangfuseBackend

    backend = LangfuseBackend()
    await backend.score(trace_id="trace-1", name="pass", value=True)

    call_kwargs = mock_langfuse.create_score.call_args[1]
    assert call_kwargs["value"] == 1.0
    assert isinstance(call_kwargs["value"], float)


@pytest.mark.asyncio
async def test_flush(mock_langfuse):
    from llmops.core.observability.langfuse_backend import LangfuseBackend

    backend = LangfuseBackend()
    await backend.flush()
    mock_langfuse.flush.assert_called()
