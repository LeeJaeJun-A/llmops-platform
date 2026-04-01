"""Repository for prompt and prompt version database operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from llmops.db.models.prompt import PromptEnvironment, PromptModel, PromptVersionModel


class PromptRepository:
    """Data access layer for prompts and prompt versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_name(self, name: str) -> PromptModel | None:
        result = await self._session.execute(select(PromptModel).where(PromptModel.name == name))
        return result.scalar_one_or_none()

    async def get_by_id(self, prompt_id: uuid.UUID) -> PromptModel | None:
        result = await self._session.execute(select(PromptModel).where(PromptModel.id == prompt_id))
        return result.scalar_one_or_none()

    async def list_active(self) -> list[PromptModel]:
        result = await self._session.execute(
            select(PromptModel)
            .where(PromptModel.is_active.is_(True))
            .options(selectinload(PromptModel.versions))
        )
        return list(result.scalars().all())

    async def create(self, name: str, description: str = "") -> PromptModel:
        prompt = PromptModel(name=name, description=description)
        self._session.add(prompt)
        await self._session.flush()
        return prompt

    async def get_version(
        self,
        prompt_id: uuid.UUID,
        version: int | None = None,
        environment: PromptEnvironment | None = None,
    ) -> PromptVersionModel | None:
        if version is not None:
            result = await self._session.execute(
                select(PromptVersionModel).where(
                    PromptVersionModel.prompt_id == prompt_id,
                    PromptVersionModel.version == version,
                )
            )
            return result.scalar_one_or_none()

        if environment is not None:
            result = await self._session.execute(
                select(PromptVersionModel)
                .where(
                    PromptVersionModel.prompt_id == prompt_id,
                    PromptVersionModel.environment == environment,
                )
                .order_by(PromptVersionModel.version.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

        # Latest version
        result = await self._session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.prompt_id == prompt_id)
            .order_by(PromptVersionModel.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_max_version(self, prompt_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(PromptVersionModel.version)).where(
                PromptVersionModel.prompt_id == prompt_id
            )
        )
        return result.scalar() or 0

    async def create_version(
        self,
        prompt_id: uuid.UUID,
        version: int,
        template: str,
        *,
        variables: dict | None = None,
        change_note: str = "",
        environment: PromptEnvironment = PromptEnvironment.DRAFT,
    ) -> PromptVersionModel:
        pv = PromptVersionModel(
            prompt_id=prompt_id,
            version=version,
            template=template,
            environment=environment,
            variables=variables or {},
            change_note=change_note,
        )
        self._session.add(pv)
        await self._session.flush()
        return pv

    async def list_versions(self, prompt_id: uuid.UUID) -> list[PromptVersionModel]:
        result = await self._session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.prompt_id == prompt_id)
            .order_by(PromptVersionModel.version.desc())
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, instance: PromptModel | PromptVersionModel) -> None:
        await self._session.refresh(instance)
