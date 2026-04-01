"""Prompt management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.api.schemas.prompts import (
    CompileRequest,
    CompileResponse,
    CreatePromptRequest,
    CreateVersionRequest,
    PromoteRequest,
    PromptResponse,
    PromptVersionResponse,
)
from llmops.core.prompts.manager import PromptManager
from llmops.core.prompts.renderer import PromptRenderer
from llmops.dependencies import get_db

router = APIRouter(prefix="/v1/prompts", tags=["prompts"])


def _get_manager(db: AsyncSession = Depends(get_db)) -> PromptManager:
    return PromptManager(db)


@router.post("", status_code=201)
async def create_prompt(
    req: CreatePromptRequest,
    manager: PromptManager = Depends(_get_manager),
) -> PromptResponse:
    """Create a new prompt with its first version (draft)."""
    try:
        result = await manager.create(
            name=req.name,
            template=req.template,
            description=req.description,
            variables=req.variables,
        )
        return PromptResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_prompts(
    manager: PromptManager = Depends(_get_manager),
) -> list[PromptResponse]:
    """List all active prompts."""
    results = await manager.list_prompts()
    return [PromptResponse(**r) for r in results]


@router.get("/{name}")
async def get_prompt(
    name: str,
    version: int | None = None,
    env: str | None = None,
    manager: PromptManager = Depends(_get_manager),
) -> PromptVersionResponse:
    """Get a prompt version by name, optional version number or environment."""
    try:
        result = await manager.get(name, version=version, environment=env)
        return PromptVersionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{name}/versions")
async def list_versions(
    name: str,
    manager: PromptManager = Depends(_get_manager),
) -> list[PromptVersionResponse]:
    """List all versions of a prompt."""
    try:
        results = await manager.list_versions(name)
        return [PromptVersionResponse(**r) for r in results]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/versions", status_code=201)
async def create_version(
    name: str,
    req: CreateVersionRequest,
    manager: PromptManager = Depends(_get_manager),
) -> PromptVersionResponse:
    """Create a new version of an existing prompt (starts as draft)."""
    try:
        result = await manager.create_version(
            name=name,
            template=req.template,
            variables=req.variables,
            change_note=req.change_note,
        )
        return PromptVersionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/compile")
async def compile_prompt(
    name: str,
    req: CompileRequest,
    manager: PromptManager = Depends(_get_manager),
) -> CompileResponse:
    """Render a prompt template with given variables."""
    try:
        version_data = await manager.get(
            name,
            version=req.version,
            environment=req.environment,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        rendered = PromptRenderer.render(version_data["template"], req.variables)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CompileResponse(
        rendered=rendered,
        template=version_data["template"],
        variables_used=req.variables,
        version=version_data["version"],
        environment=version_data["environment"],
    )


@router.post("/{name}/promote")
async def promote_prompt(
    name: str,
    req: PromoteRequest,
    manager: PromptManager = Depends(_get_manager),
) -> PromptVersionResponse:
    """Promote a prompt version to a target environment."""
    try:
        result = await manager.promote(
            name=name,
            version=req.version,
            target_env=req.target_env,
        )
        return PromptVersionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
