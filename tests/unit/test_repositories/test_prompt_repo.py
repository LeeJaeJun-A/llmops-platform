"""Tests for prompt repository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmops.db.models.prompt import PromptEnvironment, PromptModel, PromptVersionModel
from llmops.db.repositories.prompt import PromptRepository


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()  # add() is synchronous in SQLAlchemy
    return session


@pytest.fixture
def repo(mock_session):
    return PromptRepository(mock_session)


@pytest.mark.asyncio
async def test_get_by_name(repo, mock_session):
    mock_prompt = MagicMock(spec=PromptModel)
    mock_prompt.name = "test-prompt"
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_prompt
    mock_session.execute = AsyncMock(return_value=result)

    prompt = await repo.get_by_name("test-prompt")
    assert prompt is not None
    assert prompt.name == "test-prompt"
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_name_not_found(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    prompt = await repo.get_by_name("nonexistent")
    assert prompt is None


@pytest.mark.asyncio
async def test_create(repo, mock_session):
    await repo.create("new-prompt", description="A test prompt")
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, PromptModel)
    assert added.name == "new-prompt"
    assert added.description == "A test prompt"


@pytest.mark.asyncio
async def test_get_version_by_number(repo, mock_session):
    import uuid

    mock_version = MagicMock(spec=PromptVersionModel)
    mock_version.version = 2
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_version
    mock_session.execute = AsyncMock(return_value=result)

    version = await repo.get_version(uuid.uuid4(), version=2)
    assert version is not None
    assert version.version == 2


@pytest.mark.asyncio
async def test_get_version_by_environment(repo, mock_session):
    import uuid

    mock_version = MagicMock(spec=PromptVersionModel)
    mock_version.environment = PromptEnvironment.PRODUCTION
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_version
    mock_session.execute = AsyncMock(return_value=result)

    version = await repo.get_version(uuid.uuid4(), environment=PromptEnvironment.PRODUCTION)
    assert version is not None


@pytest.mark.asyncio
async def test_get_max_version(repo, mock_session):
    result = MagicMock()
    result.scalar.return_value = 5
    mock_session.execute = AsyncMock(return_value=result)

    import uuid

    max_v = await repo.get_max_version(uuid.uuid4())
    assert max_v == 5


@pytest.mark.asyncio
async def test_get_max_version_no_versions(repo, mock_session):
    result = MagicMock()
    result.scalar.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    import uuid

    max_v = await repo.get_max_version(uuid.uuid4())
    assert max_v == 0


@pytest.mark.asyncio
async def test_create_version(repo, mock_session):
    import uuid

    prompt_id = uuid.uuid4()
    await repo.create_version(
        prompt_id,
        version=3,
        template="Hello {{ name }}",
        variables={"name": "string"},
        change_note="Added name",
    )

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, PromptVersionModel)
    assert added.version == 3
    assert added.template == "Hello {{ name }}"
