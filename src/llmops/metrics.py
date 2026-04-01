"""Prometheus metrics collection and /metrics endpoint."""

import time

from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# --- HTTP request metrics ---

REQUEST_COUNT = Counter(
    "llmops_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "llmops_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# --- LLM gateway metrics ---

LLM_REQUEST_COUNT = Counter(
    "llmops_llm_requests_total",
    "Total LLM provider requests",
    ["provider", "model"],
)

LLM_REQUEST_LATENCY = Histogram(
    "llmops_llm_request_duration_seconds",
    "LLM provider request latency in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

LLM_TOKEN_COUNT = Counter(
    "llmops_llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "direction"],
)

LLM_REQUEST_ERRORS = Counter(
    "llmops_llm_request_errors_total",
    "Total LLM provider request errors",
    ["provider", "model"],
)

# --- Scoring metrics ---

SCORING_JOBS_TOTAL = Counter(
    "llmops_scoring_jobs_total",
    "Total scoring jobs processed",
    ["status"],
)

SCORING_JOB_LATENCY = Histogram(
    "llmops_scoring_job_duration_seconds",
    "Scoring job processing latency",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# --- Worker metrics ---

WORKER_RETRY_COUNT = Counter(
    "llmops_worker_retries_total",
    "Total worker job retries",
    ["worker_type"],
)

WORKER_DLQ_COUNT = Counter(
    "llmops_worker_dlq_total",
    "Total jobs sent to dead-letter queue",
    ["worker_type"],
)


def _normalize_path(path: str) -> str:
    """Normalize path for metrics labels to avoid high cardinality.

    Replaces UUID and numeric path segments with placeholders.
    """
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        # Replace UUIDs (8-4-4-4-12 hex pattern) and numeric IDs
        if len(part) == 36 and part.count("-") == 4:
            normalized.append("{id}")
        elif part.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware that records request count and latency for Prometheus."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)

        return response


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
