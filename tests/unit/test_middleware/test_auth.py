"""Tests for API key authentication middleware."""

from unittest.mock import MagicMock, patch

import pytest

from llmops.api.middleware.auth import verify_api_key


def _make_request(path: str = "/v1/chat/completions") -> MagicMock:
    request = MagicMock()
    request.url.path = path
    return request


@pytest.mark.asyncio
async def test_public_path_skips_auth():
    request = _make_request("/healthz")
    result = await verify_api_key(request, api_key=None)
    assert result == "public"


@pytest.mark.asyncio
async def test_public_paths():
    for path in ["/healthz", "/readyz", "/docs", "/redoc", "/openapi.json"]:
        request = _make_request(path)
        result = await verify_api_key(request, api_key=None)
        assert result == "public"


@pytest.mark.asyncio
async def test_no_keys_configured_allows_all():
    with patch("llmops.api.middleware.auth.settings") as mock_settings:
        mock_settings.api_key_list = []
        request = _make_request()
        result = await verify_api_key(request, api_key=None)
        assert result == "dev"


@pytest.mark.asyncio
async def test_valid_bearer_token():
    with patch("llmops.api.middleware.auth.settings") as mock_settings:
        mock_settings.api_key_list = ["my-secret-key"]
        request = _make_request()
        result = await verify_api_key(request, api_key="Bearer my-secret-key")
        assert result == "my-secret-key"


@pytest.mark.asyncio
async def test_valid_raw_token():
    with patch("llmops.api.middleware.auth.settings") as mock_settings:
        mock_settings.api_key_list = ["my-secret-key"]
        request = _make_request()
        result = await verify_api_key(request, api_key="my-secret-key")
        assert result == "my-secret-key"


@pytest.mark.asyncio
async def test_missing_header_raises_401():
    with patch("llmops.api.middleware.auth.settings") as mock_settings:
        mock_settings.api_key_list = ["my-secret-key"]
        request = _make_request()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, api_key=None)
        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_invalid_key_raises_401():
    with patch("llmops.api.middleware.auth.settings") as mock_settings:
        mock_settings.api_key_list = ["my-secret-key"]
        request = _make_request()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, api_key="Bearer wrong-key")
        assert exc_info.value.status_code == 401
        assert "Invalid" in exc_info.value.detail
