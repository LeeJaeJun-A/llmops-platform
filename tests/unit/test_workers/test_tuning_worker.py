"""Tests for tuning worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_check_running_experiments_no_experiments():
    with patch("llmops.workers.tuning_worker.async_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result)

        from llmops.workers.tuning_worker import check_running_experiments

        await check_running_experiments()
        mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_check_running_experiments_with_experiment():
    with (
        patch("llmops.workers.tuning_worker.async_session_factory") as mock_factory,
        patch("llmops.workers.tuning_worker.ExperimentRunner") as mock_runner_cls,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        mock_exp = MagicMock()
        mock_exp.id = "exp-1"
        mock_exp.name = "test-exp"

        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_exp]
        mock_session.execute = AsyncMock(return_value=result)

        mock_runner = AsyncMock()
        mock_runner.get_results = AsyncMock(
            return_value={
                "total_trials": 5,
                "results": [
                    {
                        "variant_id": "control",
                        "avg_score": 0.85,
                        "sample_count": 3,
                    }
                ],
            }
        )
        mock_runner_cls.return_value = mock_runner

        from llmops.workers.tuning_worker import check_running_experiments

        await check_running_experiments()
        mock_runner.get_results.assert_called_once_with("exp-1")


@pytest.mark.asyncio
async def test_check_experiment_retries_on_failure():
    """Test that individual experiment checks retry on failure."""
    with (
        patch("llmops.workers.tuning_worker.async_session_factory") as mock_factory,
        patch("llmops.workers.tuning_worker.ExperimentRunner") as mock_runner_cls,
        patch("llmops.workers.tuning_worker.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        mock_exp = MagicMock()
        mock_exp.id = "exp-1"
        mock_exp.name = "retry-exp"

        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_exp]
        mock_session.execute = AsyncMock(return_value=result)

        mock_runner = AsyncMock()
        # Fail twice, then succeed
        mock_runner.get_results = AsyncMock(
            side_effect=[
                RuntimeError("Transient error"),
                RuntimeError("Transient error"),
                {
                    "total_trials": 2,
                    "results": [{"variant_id": "v1", "avg_score": 0.8, "sample_count": 2}],
                },
            ]
        )
        mock_runner_cls.return_value = mock_runner

        from llmops.workers.tuning_worker import check_running_experiments

        await check_running_experiments()
        assert mock_runner.get_results.call_count == 3
