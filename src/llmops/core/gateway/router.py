"""LLM Router — resolves model to provider, executes with observability."""

from collections.abc import AsyncIterator

from llmops.core.gateway.cost_tracker import CostTracker, get_cost_tracker
from llmops.core.gateway.registry import ProviderRegistry, get_registry
from llmops.core.gateway.schemas import ChatRequest, ChatResponse, ChatResponseChunk
from llmops.core.observability.base import ObservabilityBackend


class LLMRouter:
    """Routes LLM requests to the correct provider with observability."""

    def __init__(
        self,
        registry: ProviderRegistry,
        observability: ObservabilityBackend,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self._registry = registry
        self._observability = observability
        self._cost_tracker = cost_tracker or get_cost_tracker()

    async def chat(
        self,
        request: ChatRequest,
        *,
        service_name: str = "unknown",
        request_id: str | None = None,
    ) -> ChatResponse:
        provider = self._registry.resolve(request.model)

        async with self._observability.trace(
            name="chat_completion",
            input={"messages": [m.model_dump() for m in request.messages]},
            metadata={
                "service_name": service_name,
                "request_id": request_id,
                "provider": provider.provider_name,
                "model": request.model,
            },
        ) as trace:
            response = await provider.chat(request)

            await self._observability.log_generation(
                trace_id=trace.trace_id,
                name=f"{provider.provider_name}_generation",
                model=request.model,
                input={"messages": [m.model_dump() for m in request.messages]},
                output=response.content,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                metadata={
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "finish_reason": response.choices[0].finish_reason
                    if response.choices
                    else None,
                },
            )

            await self._cost_tracker.record(
                service_name=service_name,
                model=request.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            response.metadata["trace_id"] = trace.trace_id
            return response

    async def chat_stream(
        self,
        request: ChatRequest,
        *,
        service_name: str = "unknown",
        request_id: str | None = None,
    ) -> AsyncIterator[ChatResponseChunk]:
        provider = self._registry.resolve(request.model)

        async with self._observability.trace(
            name="chat_completion_stream",
            input={"messages": [m.model_dump() for m in request.messages]},
            metadata={
                "service_name": service_name,
                "request_id": request_id,
                "provider": provider.provider_name,
                "model": request.model,
                "stream": True,
            },
        ) as trace:
            collected_content = ""
            final_usage = None

            async for chunk in provider.chat_stream(request):
                collected_content += chunk.delta_content
                if chunk.usage:
                    final_usage = chunk.usage
                yield chunk

            await self._cost_tracker.record(
                service_name=service_name,
                model=request.model,
                input_tokens=final_usage.input_tokens if final_usage else 0,
                output_tokens=final_usage.output_tokens if final_usage else 0,
            )

            await self._observability.log_generation(
                trace_id=trace.trace_id,
                name=f"{provider.provider_name}_generation",
                model=request.model,
                input={"messages": [m.model_dump() for m in request.messages]},
                output=collected_content,
                usage={
                    "input_tokens": final_usage.input_tokens if final_usage else 0,
                    "output_tokens": final_usage.output_tokens if final_usage else 0,
                    "total_tokens": final_usage.total_tokens if final_usage else 0,
                },
                metadata={
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": True,
                },
            )


def get_llm_router(observability: ObservabilityBackend) -> LLMRouter:
    return LLMRouter(registry=get_registry(), observability=observability)
