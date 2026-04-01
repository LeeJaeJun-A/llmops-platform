"""Tests for rate limiting middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from llmops.api.middleware.rate_limit import RateLimiter, rate_limit_dependency


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    with patch("llmops.api.middleware.rate_limit.aioredis") as mock_aioredis:
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock()
        mock_pipe.zcard = MagicMock()
        mock_pipe.zadd = MagicMock()
        mock_pipe.expire = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[None, 5, None, None])

        mock_client = AsyncMock()
        mock_client.pipeline = MagicMock(return_value=mock_pipe)
        mock_aioredis.from_url.return_value = mock_client

        limiter = RateLimiter(redis_url="redis://localhost", requests_per_minute=60)
        await limiter.check("test-key")  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    with patch("llmops.api.middleware.rate_limit.aioredis") as mock_aioredis:
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock()
        mock_pipe.zcard = MagicMock()
        mock_pipe.zadd = MagicMock()
        mock_pipe.expire = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[None, 60, None, None])

        mock_client = AsyncMock()
        mock_client.pipeline = MagicMock(return_value=mock_pipe)
        mock_aioredis.from_url.return_value = mock_client

        limiter = RateLimiter(redis_url="redis://localhost", requests_per_minute=60)
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("test-key")
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_rate_limiter_disabled_when_rpm_zero():
    limiter = RateLimiter(redis_url="redis://localhost", requests_per_minute=0)
    await limiter.check("test-key")  # Should not raise, no Redis call


@pytest.mark.asyncio
async def test_rate_limit_dependency_graceful_degradation():
    """Rate limiter should allow requests when Redis is unavailable."""
    request = MagicMock()
    request.headers.get.return_value = "test-service"
    request.client.host = "127.0.0.1"

    with patch("llmops.api.middleware.rate_limit.get_rate_limiter") as mock_get:
        mock_limiter = AsyncMock()
        mock_limiter.check = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_get.return_value = mock_limiter

        # Should not raise despite Redis error
        await rate_limit_dependency(request)


@pytest.mark.asyncio
async def test_rate_limit_dependency_propagates_429():
    """Rate limiter should still propagate 429 errors."""
    request = MagicMock()
    request.headers.get.return_value = "test-service"
    request.client.host = "127.0.0.1"

    with patch("llmops.api.middleware.rate_limit.get_rate_limiter") as mock_get:
        mock_limiter = AsyncMock()
        mock_limiter.check = AsyncMock(
            side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
        )
        mock_get.return_value = mock_limiter

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit_dependency(request)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_dependency_uses_service_name():
    """Should use X-Service-Name header as the rate limit key."""
    request = MagicMock()
    request.headers.get.return_value = "my-service"
    request.client.host = "127.0.0.1"

    with patch("llmops.api.middleware.rate_limit.get_rate_limiter") as mock_get:
        mock_limiter = AsyncMock()
        mock_limiter.check = AsyncMock()
        mock_get.return_value = mock_limiter

        await rate_limit_dependency(request)
        mock_limiter.check.assert_called_once_with("my-service")


@pytest.mark.asyncio
async def test_rate_limit_dependency_falls_back_to_ip():
    """Should use client IP when X-Service-Name is empty."""
    request = MagicMock()
    request.headers.get.return_value = ""
    request.client.host = "192.168.1.1"

    with patch("llmops.api.middleware.rate_limit.get_rate_limiter") as mock_get:
        mock_limiter = AsyncMock()
        mock_limiter.check = AsyncMock()
        mock_get.return_value = mock_limiter

        await rate_limit_dependency(request)
        mock_limiter.check.assert_called_once_with("192.168.1.1")
