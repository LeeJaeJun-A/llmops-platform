"""Tests for scoring worker."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llmops.core.scoring.base import PipelineResult, ScoreResult


@pytest.fixture
def sample_job():
    return {
        "trace_id": "trace-123",
        "pipeline_id": "pipe-1",
        "input_text": "What is 2+2?",
        "output_text": "4",
        "reference_text": "4",
        "scorers_config": [
            {"strategy": "rule_based", "weight": 1.0, "config": {}}
        ],
        "_retry_count": 0,
    }


@pytest.fixture
def mock_pipeline_result():
    return PipelineResult(
        aggregate_score=0.9,
        individual_scores=[
            ScoreResult(name="rule_based", value=0.9, comment="Good", metadata={})
        ],
    )


@pytest.mark.asyncio
async def test_process_job(sample_job, mock_pipeline_result):
    with (
        patch(
            "llmops.workers.scoring_worker.ScoringPipeline"
        ) as mock_pipeline_cls,
        patch(
            "llmops.workers.scoring_worker.async_session_factory"
        ) as mock_session_factory,
        patch(
            "llmops.workers.scoring_worker.get_observability_backend"
        ) as mock_obs_fn,
    ):
        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=mock_pipeline_result)
        mock_pipeline_cls.return_value = mock_pipeline

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        mock_obs = AsyncMock()
        mock_obs_fn.return_value = mock_obs

        from llmops.workers.scoring_worker import process_job

        await process_job(sample_job)

        mock_pipeline.run.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_obs.score.assert_called()
        mock_obs.flush.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_scoring_job():
    mock_redis = AsyncMock()

    from llmops.workers.scoring_worker import enqueue_scoring_job

    await enqueue_scoring_job(
        mock_redis,
        trace_id="trace-1",
        pipeline_id="pipe-1",
        input_text="input",
        output_text="output",
        scorers_config=[{"strategy": "rule_based"}],
    )

    mock_redis.lpush.assert_called_once()
    call_args = mock_redis.lpush.call_args
    assert call_args[0][0] == "llmops:scoring:queue"
    # Verify retry count is included
    job_data = json.loads(call_args[0][1])
    assert job_data["_retry_count"] == 0


@pytest.mark.asyncio
async def test_handle_job_with_retry_success():
    """Test successful job processing."""
    job_data = {
        "trace_id": "trace-1",
        "pipeline_id": "pipe-1",
        "input_text": "in",
        "output_text": "out",
        "scorers_config": [],
        "_retry_count": 0,
    }
    job_json = json.dumps(job_data)
    mock_redis = AsyncMock()

    with patch("llmops.workers.scoring_worker.process_job", new_callable=AsyncMock) as mock_process:
        from llmops.workers.scoring_worker import _handle_job_with_retry

        await _handle_job_with_retry(mock_redis, job_json)
        mock_process.assert_called_once()
        mock_redis.lpush.assert_not_called()


@pytest.mark.asyncio
async def test_handle_job_with_retry_requeues_on_failure():
    """Test that failed jobs are requeued with incremented retry count."""
    job_data = {
        "trace_id": "trace-1",
        "pipeline_id": "pipe-1",
        "input_text": "in",
        "output_text": "out",
        "scorers_config": [],
        "_retry_count": 0,
    }
    job_json = json.dumps(job_data)
    mock_redis = AsyncMock()

    with (
        patch(
            "llmops.workers.scoring_worker.process_job",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB error"),
        ),
        patch("llmops.workers.scoring_worker.asyncio.sleep", new_callable=AsyncMock),
    ):
        from llmops.workers.scoring_worker import _handle_job_with_retry

        await _handle_job_with_retry(mock_redis, job_json)

        # Should requeue with incremented retry count
        mock_redis.lpush.assert_called_once()
        requeued_data = json.loads(mock_redis.lpush.call_args[0][1])
        assert requeued_data["_retry_count"] == 1
        assert mock_redis.lpush.call_args[0][0] == "llmops:scoring:queue"


@pytest.mark.asyncio
async def test_handle_job_sends_to_dlq_after_max_retries():
    """Test that jobs are sent to DLQ after max retries."""
    job_data = {
        "trace_id": "trace-1",
        "pipeline_id": "pipe-1",
        "input_text": "in",
        "output_text": "out",
        "scorers_config": [],
        "_retry_count": 3,
    }
    job_json = json.dumps(job_data)
    mock_redis = AsyncMock()

    with patch(
        "llmops.workers.scoring_worker.process_job",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Persistent error"),
    ):
        from llmops.workers.scoring_worker import _handle_job_with_retry

        await _handle_job_with_retry(mock_redis, job_json)

        # Should send to DLQ
        mock_redis.lpush.assert_called_once()
        assert mock_redis.lpush.call_args[0][0] == "llmops:scoring:dlq"
