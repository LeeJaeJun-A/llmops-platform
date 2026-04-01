"""Unified request/response models for all LLM providers."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=128000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stop: list[str] | None = None
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class Choice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: str = "stop"


class ChatResponse(BaseModel):
    id: str
    model: str
    choices: list[Choice]
    usage: Usage
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def content(self) -> str:
        if self.choices:
            return self.choices[0].message.content
        return ""


class ChatResponseChunk(BaseModel):
    id: str
    model: str
    delta_content: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None
