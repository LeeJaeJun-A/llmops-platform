"""Gateway endpoint — /v1/chat/completions."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.api.middleware.rate_limit import rate_limit_dependency
from llmops.api.schemas.completions import (
    ChoiceResponse,
    CompletionRequest,
    CompletionResponse,
    UsageResponse,
)
from llmops.core.gateway.router import LLMRouter, get_llm_router
from llmops.core.gateway.schemas import ChatRequest, Message, Role
from llmops.core.observability.base import ObservabilityBackend
from llmops.core.prompts.manager import PromptManager
from llmops.core.prompts.renderer import PromptRenderer
from llmops.dependencies import get_db, get_observability_backend

router = APIRouter(prefix="/v1", tags=["gateway"], dependencies=[Depends(rate_limit_dependency)])


async def _resolve_prompt(req: CompletionRequest, db: AsyncSession) -> CompletionRequest:
    """If prompt_name is set, resolve and render the prompt into messages."""
    if not req.prompt_name:
        return req

    manager = PromptManager(db)
    version_data = await manager.get(
        req.prompt_name,
        version=req.prompt_version,
        environment=req.prompt_env,
    )

    rendered = PromptRenderer.render(version_data["template"], req.prompt_variables)

    # Prepend the rendered prompt as a system message, keep existing messages
    prompt_message = {"role": "system", "content": rendered}
    req.messages = [prompt_message] + req.messages
    req.metadata["prompt_name"] = req.prompt_name
    req.metadata["prompt_version"] = version_data["version"]
    req.metadata["prompt_environment"] = version_data["environment"]

    return req


def _to_chat_request(req: CompletionRequest) -> ChatRequest:
    """Convert API request to internal ChatRequest."""
    messages = []
    for msg in req.messages:
        role = Role(msg.get("role", "user"))
        content = msg.get("content", "")
        messages.append(Message(role=role, content=content))

    return ChatRequest(
        model=req.model,
        messages=messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        top_p=req.top_p,
        stop=req.stop,
        stream=req.stream,
        metadata=req.metadata,
    )


def _get_router(
    observability: ObservabilityBackend = Depends(get_observability_backend),
) -> LLMRouter:
    return get_llm_router(observability)


@router.post("/chat/completions", response_model=None)
async def chat_completions(
    req: CompletionRequest,
    db: AsyncSession = Depends(get_db),
    llm_router: LLMRouter = Depends(_get_router),
    x_service_name: str = Header(default="unknown", alias="X-Service-Name"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> CompletionResponse | StreamingResponse:
    # Resolve managed prompt if specified
    req = await _resolve_prompt(req, db)

    chat_request = _to_chat_request(req)

    if req.stream:
        return StreamingResponse(
            _stream_response(llm_router, chat_request, x_service_name, x_request_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    response = await llm_router.chat(
        chat_request,
        service_name=x_service_name,
        request_id=x_request_id,
    )

    return CompletionResponse(
        id=response.id,
        model=response.model,
        choices=[
            ChoiceResponse(
                index=c.index,
                message={"role": c.message.role.value, "content": c.message.content},
                finish_reason=c.finish_reason,
            )
            for c in response.choices
        ],
        usage=UsageResponse(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
        ),
        metadata=response.metadata,
    )


async def _stream_response(
    llm_router: LLMRouter,
    chat_request: ChatRequest,
    service_name: str,
    request_id: str | None,
) -> AsyncIterator[str]:
    """Generate SSE events for streaming responses."""
    async for chunk in llm_router.chat_stream(
        chat_request,
        service_name=service_name,
        request_id=request_id,
    ):
        data = {
            "id": chunk.id,
            "model": chunk.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk.delta_content} if chunk.delta_content else {},
                    "finish_reason": chunk.finish_reason,
                }
            ],
        }
        if chunk.usage:
            data["usage"] = {  # type: ignore[assignment]
                "input_tokens": chunk.usage.input_tokens,
                "output_tokens": chunk.usage.output_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }
        yield f"data: {json.dumps(data)}\n\n"

    yield "data: [DONE]\n\n"
