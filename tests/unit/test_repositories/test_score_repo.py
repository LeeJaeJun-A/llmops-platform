"""Tests for score repository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmops.db.models.score import ScoreResultModel, ScoringPipelineModel
from llmops.db.repositories.score import ScoreRepository


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()  # add() is synchronous in SQLAlchemy
    return session


@pytest.fixture
def repo(mock_session):
    return ScoreRepository(mock_session)


@pytest.mark.asyncio
async def test_get_pipeline_by_id(repo, mock_session):
    mock_pipeline = MagicMock(spec=ScoringPipelineModel)
    mock_pipeline.name = "quality"
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_pipeline
    mock_session.execute = AsyncMock(return_value=result)

    pipeline = await repo.get_pipeline_by_id("pipe-1")
    assert pipeline is not None
    assert pipeline.name == "quality"


@pytest.mark.asyncio
async def test_get_pipeline_by_name(repo, mock_session):
    mock_pipeline = MagicMock(spec=ScoringPipelineModel)
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_pipeline
    mock_session.execute = AsyncMock(return_value=result)

    pipeline = await repo.get_pipeline_by_name("quality")
    assert pipeline is not None


@pytest.mark.asyncio
async def test_list_active_pipelines(repo, mock_session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        MagicMock(spec=ScoringPipelineModel),
    ]
    mock_session.execute = AsyncMock(return_value=result)

    pipelines = await repo.list_active_pipelines()
    assert len(pipelines) == 1


@pytest.mark.asyncio
async def test_create_pipeline(repo, mock_session):
    await repo.create_pipeline(
        name="quality-check",
        scorers_config=[{"strategy": "rule_based"}],
    )
    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, ScoringPipelineModel)
    assert added.name == "quality-check"


@pytest.mark.asyncio
async def test_get_results_by_trace(repo, mock_session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        MagicMock(spec=ScoreResultModel),
        MagicMock(spec=ScoreResultModel),
    ]
    mock_session.execute = AsyncMock(return_value=result)

    results = await repo.get_results_by_trace("trace-1")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_create_result(repo, mock_session):
    import uuid

    await repo.create_result(
        pipeline_id=uuid.uuid4(),
        trace_id="trace-1",
        input_text="input",
        output_text="output",
        aggregate_score=0.85,
        individual_scores=[],
    )
    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, ScoreResultModel)
