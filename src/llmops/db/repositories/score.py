"""Repository for scoring pipeline and result database operations."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.db.models.score import ScoreResultModel, ScoringPipelineModel


class ScoreRepository:
    """Data access layer for scoring pipelines and results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pipeline_by_id(self, pipeline_id: str | uuid.UUID) -> ScoringPipelineModel | None:
        result = await self._session.execute(
            select(ScoringPipelineModel).where(ScoringPipelineModel.id == pipeline_id)
        )
        return result.scalar_one_or_none()

    async def get_pipeline_by_name(self, name: str) -> ScoringPipelineModel | None:
        result = await self._session.execute(
            select(ScoringPipelineModel).where(ScoringPipelineModel.name == name)
        )
        return result.scalar_one_or_none()

    async def list_active_pipelines(self) -> list[ScoringPipelineModel]:
        result = await self._session.execute(
            select(ScoringPipelineModel).where(ScoringPipelineModel.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def create_pipeline(self, **kwargs: Any) -> ScoringPipelineModel:
        pipeline = ScoringPipelineModel(**kwargs)
        self._session.add(pipeline)
        await self._session.flush()
        return pipeline

    async def get_results_by_trace(self, trace_id: str) -> list[ScoreResultModel]:
        result = await self._session.execute(
            select(ScoreResultModel).where(ScoreResultModel.trace_id == trace_id)
        )
        return list(result.scalars().all())

    async def create_result(self, **kwargs: Any) -> ScoreResultModel:
        record = ScoreResultModel(**kwargs)
        self._session.add(record)
        await self._session.flush()
        return record

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, instance: ScoringPipelineModel | ScoreResultModel) -> None:
        await self._session.refresh(instance)
