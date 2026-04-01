from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sqlalchemy
from fastapi import Depends, FastAPI

from llmops.api.middleware.auth import verify_api_key
from llmops.api.middleware.request_context import RequestContextMiddleware
from llmops.api.v1 import admin, gateway, prompts, scoring, tuning
from llmops.config import settings
from llmops.logging import get_logger, setup_logging
from llmops.metrics import PrometheusMiddleware, metrics_endpoint

logger = get_logger(__name__)


def _register_providers() -> None:
    """Register all configured LLM providers."""
    from llmops.core.gateway.registry import registry

    if settings.anthropic_api_key:
        from llmops.core.gateway.anthropic import AnthropicProvider

        registry.register(AnthropicProvider())

    if settings.gemini_api_key:
        from llmops.core.gateway.gemini import GeminiProvider

        registry.register(GeminiProvider())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    setup_logging()
    logger.info("starting_up", env=settings.app_env.value)

    from llmops.db.session import engine

    async with engine.connect() as conn:
        await conn.execute(sqlalchemy.text("SELECT 1"))

    _register_providers()
    logger.info("startup_complete")

    yield

    # Shutdown
    logger.info("shutting_down")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="LLMOps Platform",
        description="General-purpose LLMOps microservice with scoring, tuning, and observability",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        dependencies=[Depends(verify_api_key)],
    )

    # Middleware (executed in reverse order of registration)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(PrometheusMiddleware)

    # Routers
    app.include_router(admin.router)
    app.include_router(gateway.router)
    app.include_router(scoring.router)
    app.include_router(prompts.router)
    app.include_router(tuning.router)

    # Prometheus metrics endpoint (no auth required)
    app.add_route("/metrics", metrics_endpoint)

    return app


app = create_app()
