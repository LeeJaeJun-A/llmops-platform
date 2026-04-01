"""Anthropic (Claude) provider implementation."""

import uuid
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from llmops.config import settings
from llmops.core.gateway.base import LLMProvider
from llmops.core.gateway.schemas import (
    ChatRequest,
    ChatResponse,
    ChatResponseChunk,
    Choice,
    Message,
    Role,
    Usage,
)

ANTHROPIC_MODELS = [
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    "claude-haiku-4-20250506",
]


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def supports_model(self, model: str) -> bool:
        return model in ANTHROPIC_MODELS or model.startswith("claude-")

    def _build_params(self, request: ChatRequest) -> dict:
        """Convert unified ChatRequest to Anthropic API parameters."""
        system_message: str | None = None
        messages = []

        for msg in request.messages:
            if msg.role == Role.SYSTEM:
                system_message = msg.content
            else:
                messages.append(
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                    }
                )

        params: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if system_message:
            params["system"] = system_message

        if request.stop:
            params["stop_sequences"] = request.stop

        return params

    async def chat(self, request: ChatRequest) -> ChatResponse:
        params = self._build_params(request)
        response = await self._client.messages.create(**params)

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return ChatResponse(
            id=response.id,
            model=response.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role=Role.ASSISTANT, content=content),
                    finish_reason=response.stop_reason or "stop",
                )
            ],
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatResponseChunk]:
        params = self._build_params(request)
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        async with self._client.messages.stream(**params) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield ChatResponseChunk(
                            id=response_id,
                            model=request.model,
                            delta_content=event.delta.text,
                        )
                elif event.type == "message_stop":
                    final = stream.current_message_snapshot
                    yield ChatResponseChunk(
                        id=response_id,
                        model=request.model,
                        finish_reason=final.stop_reason or "stop",
                        usage=Usage(
                            input_tokens=final.usage.input_tokens,
                            output_tokens=final.usage.output_tokens,
                            total_tokens=final.usage.input_tokens + final.usage.output_tokens,
                        ),
                    )
