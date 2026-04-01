"""Tests for noop observability backend."""

import pytest

from llmops.core.observability.noop_backend import NoopBackend


@pytest.mark.asyncio
async def test_trace_yields_trace_with_uuid():
    backend = NoopBackend()
    async with backend.trace("test-trace", input="test") as trace:
        assert trace.trace_id
        assert trace.name == "test-trace"
        assert len(trace.trace_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_log_generation_noop():
    backend = NoopBackend()
    # Should not raise
    await backend.log_generation(
        trace_id="trace-1",
        name="gen",
        model="test-model",
        input="input",
        output="output",
        usage={"input_tokens": 5, "output_tokens": 3},
    )


@pytest.mark.asyncio
async def test_score_noop():
    backend = NoopBackend()
    await backend.score(trace_id="trace-1", name="accuracy", value=0.95)
    await backend.score(trace_id="trace-1", name="flag", value=True)
    await backend.score(trace_id="trace-1", name="grade", value="A")


@pytest.mark.asyncio
async def test_flush_noop():
    backend = NoopBackend()
    await backend.flush()
