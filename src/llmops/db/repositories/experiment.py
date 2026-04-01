"""Repository for experiment and trial database operations."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.db.models.experiment import ExperimentModel, ExperimentTrialModel


class ExperimentRepository:
    """Data access layer for experiments and trials."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, experiment_id: str) -> ExperimentModel | None:
        result = await self._session.execute(
            select(ExperimentModel).where(ExperimentModel.id == experiment_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[ExperimentModel]:
        result = await self._session.execute(
            select(ExperimentModel).order_by(ExperimentModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: str) -> list[ExperimentModel]:
        result = await self._session.execute(
            select(ExperimentModel).where(ExperimentModel.status == status)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ExperimentModel:
        experiment = ExperimentModel(**kwargs)
        self._session.add(experiment)
        await self._session.flush()
        return experiment

    async def get_scored_trials(self, experiment_id: str | uuid.UUID) -> list[ExperimentTrialModel]:
        result = await self._session.execute(
            select(ExperimentTrialModel).where(
                ExperimentTrialModel.experiment_id == experiment_id,
                ExperimentTrialModel.score.isnot(None),
            )
        )
        return list(result.scalars().all())

    async def create_trial(self, **kwargs: Any) -> ExperimentTrialModel:
        trial = ExperimentTrialModel(**kwargs)
        self._session.add(trial)
        await self._session.flush()
        return trial

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, instance: ExperimentModel | ExperimentTrialModel) -> None:
        await self._session.refresh(instance)
