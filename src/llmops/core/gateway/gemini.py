"""Google Gemini provider implementation."""

import uuid
from collections.abc import AsyncIterator

from google import genai
from google.genai.types import Content, GenerateContentConfig, Part

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

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite-001",
    "gemini-3-flash-preview",
]


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def supports_model(self, model: str) -> bool:
        return model in GEMINI_MODELS or model.startswith("gemini-")

    def _build_contents(self, request: ChatRequest) -> tuple[list[Content], str | None]:
        """Convert unified messages to Gemini Content format.

        Returns (contents, system_instruction).
        """
        system_instruction: str | None = None
        contents: list[Content] = []

        for msg in request.messages:
            if msg.role == Role.SYSTEM:
                system_instruction = msg.content
            else:
                # Gemini uses "model" instead of "assistant"
                role = "model" if msg.role == Role.ASSISTANT else "user"
                contents.append(Content(role=role, parts=[Part(text=msg.content)]))

        return contents, system_instruction

    def _build_config(
        self, request: ChatRequest, system_instruction: str | None
    ) -> GenerateContentConfig:
        config = GenerateContentConfig(
            temperature=request.temperature,
            top_p=request.top_p,
            max_output_tokens=request.max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction
        if request.stop:
            config.stop_sequences = request.stop
        return config

    async def chat(self, request: ChatRequest) -> ChatResponse:
        contents, system_instruction = self._build_contents(request)
        config = self._build_config(request, system_instruction)

        response = await self._client.aio.models.generate_content(
            model=request.model,
            contents=contents,  # type: ignore[arg-type]
            config=config,
        )

        content = ""
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if part.text:
                    content += part.text

        finish_reason = "stop"
        if response.candidates and response.candidates[0].finish_reason:
            raw_reason = str(response.candidates[0].finish_reason).lower()
            if "max_tokens" in raw_reason:
                finish_reason = "length"
            elif "safety" in raw_reason:
                finish_reason = "content_filter"

        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

        return ChatResponse(
            id=response.response_id or f"chatcmpl-{uuid.uuid4().hex[:12]}",
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role=Role.ASSISTANT, content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatResponseChunk]:
        contents, system_instruction = self._build_contents(request)
        config = self._build_config(request, system_instruction)
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        stream = await self._client.aio.models.generate_content_stream(
            model=request.model,
            contents=contents,  # type: ignore[arg-type]
            config=config,
        )

        async for chunk in stream:
            if (
                chunk.candidates
                and chunk.candidates[0].content
                and chunk.candidates[0].content.parts
            ):
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        yield ChatResponseChunk(
                            id=response_id,
                            model=request.model,
                            delta_content=part.text,
                        )

                # Check for finish reason on each chunk
                if chunk.candidates[0].finish_reason:
                    usage = None
                    if chunk.usage_metadata:
                        input_tokens = chunk.usage_metadata.prompt_token_count or 0
                        output_tokens = chunk.usage_metadata.candidates_token_count or 0
                        usage = Usage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=input_tokens + output_tokens,
                        )
                    yield ChatResponseChunk(
                        id=response_id,
                        model=request.model,
                        finish_reason="stop",
                        usage=usage,
                    )
