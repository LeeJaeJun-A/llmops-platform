"""Tests for experiment repository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmops.db.models.experiment import ExperimentModel, ExperimentTrialModel
from llmops.db.repositories.experiment import ExperimentRepository


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()  # add() is synchronous in SQLAlchemy
    return session


@pytest.fixture
def repo(mock_session):
    return ExperimentRepository(mock_session)


@pytest.mark.asyncio
async def test_get_by_id(repo, mock_session):
    mock_exp = MagicMock(spec=ExperimentModel)
    mock_exp.name = "test-exp"
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_exp
    mock_session.execute = AsyncMock(return_value=result)

    exp = await repo.get_by_id("exp-123")
    assert exp is not None
    assert exp.name == "test-exp"


@pytest.mark.asyncio
async def test_get_by_id_not_found(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    exp = await repo.get_by_id("nonexistent")
    assert exp is None


@pytest.mark.asyncio
async def test_list_all(repo, mock_session):
    mock_exp1 = MagicMock(spec=ExperimentModel)
    mock_exp2 = MagicMock(spec=ExperimentModel)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [mock_exp1, mock_exp2]
    mock_session.execute = AsyncMock(return_value=result)

    exps = await repo.list_all()
    assert len(exps) == 2


@pytest.mark.asyncio
async def test_create(repo, mock_session):
    await repo.create(
        name="new-exp",
        status="draft",
        parameter_space={},
        variants=[],
    )
    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, ExperimentModel)
    assert added.name == "new-exp"


@pytest.mark.asyncio
async def test_create_trial(repo, mock_session):
    import uuid

    await repo.create_trial(
        experiment_id=uuid.uuid4(),
        variant_id="v-1",
        trace_id="trace-1",
        parameters={"temp": 0.7},
        input_text="hello",
        output_text="world",
        score=0.9,
    )

    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, ExperimentTrialModel)
    assert added.variant_id == "v-1"
    assert added.score == 0.9


@pytest.mark.asyncio
async def test_list_by_status(repo, mock_session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)

    exps = await repo.list_by_status("running")
    assert exps == []
    mock_session.execute.assert_called_once()
