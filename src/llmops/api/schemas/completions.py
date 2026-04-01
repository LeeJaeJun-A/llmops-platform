"""API request/response schemas for the completions endpoint."""

from typing import Any

from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=128000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stop: list[str] | None = None
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Prompt integration: resolve a managed prompt instead of raw messages
    prompt_name: str | None = None
    prompt_version: int | None = None
    prompt_env: str | None = None
    prompt_variables: dict[str, str] = Field(default_factory=dict)


class UsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ChoiceResponse(BaseModel):
    index: int
    message: dict[str, str]
    finish_reason: str


class CompletionResponse(BaseModel):
    id: str
    model: str
    choices: list[ChoiceResponse]
    usage: UsageResponse
    metadata: dict[str, Any] = Field(default_factory=dict)
