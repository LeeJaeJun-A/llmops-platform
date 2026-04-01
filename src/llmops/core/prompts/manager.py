"""Prompt manager — CRUD, versioning, promotion with PostgreSQL backend."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from llmops.core.prompts.base import PromptStore
from llmops.db.models.prompt import PromptEnvironment, PromptModel, PromptVersionModel


def _version_to_dict(v: PromptVersionModel) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "prompt_id": str(v.prompt_id),
        "version": v.version,
        "template": v.template,
        "environment": v.environment.value,
        "variables": v.variables,
        "change_note": v.change_note,
        "created_at": v.created_at.isoformat(),
    }


def _prompt_to_dict(
    p: PromptModel, latest_version: PromptVersionModel | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
    }
    if latest_version:
        result["latest_version"] = _version_to_dict(latest_version)
    return result


class PromptManager(PromptStore):
    """PostgreSQL-backed prompt management with versioning and environment promotion."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        name: str,
        *,
        version: int | None = None,
        environment: str | None = None,
    ) -> dict[str, Any]:
        """Get a prompt version by name + version number or environment label."""
        prompt = await self._get_prompt_by_name(name)

        if version is not None:
            result = await self._session.execute(
                select(PromptVersionModel).where(
                    PromptVersionModel.prompt_id == prompt.id,
                    PromptVersionModel.version == version,
                )
            )
            pv = result.scalar_one_or_none()
            if not pv:
                raise ValueError(f"Version {version} not found for prompt '{name}'")
            return _version_to_dict(pv)

        if environment:
            env = PromptEnvironment(environment)
            result = await self._session.execute(
                select(PromptVersionModel)
                .where(
                    PromptVersionModel.prompt_id == prompt.id,
                    PromptVersionModel.environment == env,
                )
                .order_by(PromptVersionModel.version.desc())
                .limit(1)
            )
            pv = result.scalar_one_or_none()
            if not pv:
                raise ValueError(f"No version in '{environment}' environment for prompt '{name}'")
            return _version_to_dict(pv)

        # Default: latest version
        result = await self._session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.prompt_id == prompt.id)
            .order_by(PromptVersionModel.version.desc())
            .limit(1)
        )
        pv = result.scalar_one_or_none()
        if not pv:
            raise ValueError(f"No versions found for prompt '{name}'")
        return _version_to_dict(pv)

    async def create(
        self,
        name: str,
        template: str,
        *,
        description: str = "",
        variables: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new prompt with its first version."""
        prompt = PromptModel(name=name, description=description)
        self._session.add(prompt)
        await self._session.flush()

        version = PromptVersionModel(
            prompt_id=prompt.id,
            version=1,
            template=template,
            environment=PromptEnvironment.DRAFT,
            variables=variables or {},
        )
        self._session.add(version)
        await self._session.commit()
        await self._session.refresh(prompt)
        await self._session.refresh(version)

        return _prompt_to_dict(prompt, latest_version=version)

    async def create_version(
        self,
        name: str,
        template: str,
        *,
        variables: dict | None = None,
        change_note: str = "",
    ) -> dict[str, Any]:
        """Create a new version of an existing prompt."""
        prompt = await self._get_prompt_by_name(name)

        # Get next version number
        result = await self._session.execute(
            select(func.max(PromptVersionModel.version)).where(
                PromptVersionModel.prompt_id == prompt.id
            )
        )
        max_version = result.scalar() or 0

        version = PromptVersionModel(
            prompt_id=prompt.id,
            version=max_version + 1,
            template=template,
            environment=PromptEnvironment.DRAFT,
            variables=variables or {},
            change_note=change_note,
        )
        self._session.add(version)
        await self._session.commit()
        await self._session.refresh(version)

        return _version_to_dict(version)

    async def promote(
        self,
        name: str,
        version: int,
        target_env: str,
    ) -> dict[str, Any]:
        """Promote a version to a target environment (draft -> staging -> production)."""
        prompt = await self._get_prompt_by_name(name)
        env = PromptEnvironment(target_env)

        result = await self._session.execute(
            select(PromptVersionModel).where(
                PromptVersionModel.prompt_id == prompt.id,
                PromptVersionModel.version == version,
            )
        )
        pv = result.scalar_one_or_none()
        if not pv:
            raise ValueError(f"Version {version} not found for prompt '{name}'")

        pv.environment = env
        await self._session.commit()
        await self._session.refresh(pv)

        return _version_to_dict(pv)

    async def list_prompts(self) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(PromptModel)
            .where(PromptModel.is_active.is_(True))
            .options(selectinload(PromptModel.versions))
        )
        prompts = result.scalars().all()

        return [
            _prompt_to_dict(p, latest_version=p.versions[0] if p.versions else None)
            for p in prompts
        ]

    async def list_versions(self, name: str) -> list[dict[str, Any]]:
        prompt = await self._get_prompt_by_name(name)

        result = await self._session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.prompt_id == prompt.id)
            .order_by(PromptVersionModel.version.desc())
        )
        versions = result.scalars().all()
        return [_version_to_dict(v) for v in versions]

    async def _get_prompt_by_name(self, name: str) -> PromptModel:
        result = await self._session.execute(select(PromptModel).where(PromptModel.name == name))
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise ValueError(f"Prompt '{name}' not found")
        return prompt
