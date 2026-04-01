"""API key authentication middleware."""

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from llmops.config import settings

_api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# Paths that don't require authentication
_PUBLIC_PATHS = {"/healthz", "/readyz", "/metrics", "/docs", "/redoc", "/openapi.json"}


async def verify_api_key(request: Request, api_key: str | None = Security(_api_key_header)) -> str:
    """Verify the API key from the Authorization header.

    Expects: Authorization: Bearer <key>
    """
    if request.url.path in _PUBLIC_PATHS:
        return "public"

    if not settings.api_key_list:
        # No keys configured = auth disabled (development mode)
        return "dev"

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Strip "Bearer " prefix if present
    key = api_key.removeprefix("Bearer ").strip()

    if key not in settings.api_key_list:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return key
