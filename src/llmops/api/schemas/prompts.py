"""API schemas for prompt management endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class CreatePromptRequest(BaseModel):
    name: str
    template: str
    description: str = ""
    variables: dict[str, str] = Field(default_factory=dict)


class CreateVersionRequest(BaseModel):
    template: str
    variables: dict[str, str] = Field(default_factory=dict)
    change_note: str = ""


class CompileRequest(BaseModel):
    variables: dict[str, str]
    version: int | None = None
    environment: str | None = None


class PromoteRequest(BaseModel):
    version: int
    target_env: str  # draft, staging, production


class PromptVersionResponse(BaseModel):
    id: str
    prompt_id: str
    version: int
    template: str
    environment: str
    variables: dict[str, Any]
    change_note: str
    created_at: str


class PromptResponse(BaseModel):
    id: str
    name: str
    description: str
    is_active: bool
    created_at: str
    latest_version: PromptVersionResponse | None = None


class CompileResponse(BaseModel):
    rendered: str
    template: str
    variables_used: dict[str, str]
    version: int
    environment: str
