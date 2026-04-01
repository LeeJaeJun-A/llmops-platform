"""Background scoring worker — consumes scoring jobs from Redis queue."""

import asyncio
import json
import signal
import time

import redis.asyncio as aioredis

from llmops.config import settings
from llmops.core.scoring.base import ScorerConfig
from llmops.core.scoring.pipeline import ScoringPipeline
from llmops.db.models.score import ScoreResultModel
from llmops.db.session import async_session_factory
from llmops.dependencies import get_observability_backend
from llmops.logging import get_logger, setup_logging
from llmops.metrics import (
    SCORING_JOB_LATENCY,
    SCORING_JOBS_TOTAL,
    WORKER_DLQ_COUNT,
    WORKER_RETRY_COUNT,
)

logger = get_logger(__name__)

SCORING_QUEUE = "llmops:scoring:queue"
SCORING_DLQ = "llmops:scoring:dlq"
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0


async def enqueue_scoring_job(
    redis: aioredis.Redis,
    *,
    trace_id: str,
    pipeline_id: str,
    input_text: str,
    output_text: str,
    reference_text: str | None = None,
    scorers_config: list[dict],
) -> None:
    """Push a scoring job onto the Redis queue."""
    job = json.dumps(
        {
            "trace_id": trace_id,
            "pipeline_id": pipeline_id,
            "input_text": input_text,
            "output_text": output_text,
            "reference_text": reference_text,
            "scorers_config": scorers_config,
            "_retry_count": 0,
        }
    )
    await redis.lpush(SCORING_QUEUE, job)  # type: ignore[misc]


async def process_job(job_data: dict) -> None:
    """Process a single scoring job."""
    scorer_configs = [
        ScorerConfig(
            strategy=s["strategy"],
            weight=s.get("weight", 1.0),
            config=s.get("config", {}),
        )
        for s in job_data["scorers_config"]
    ]

    pipeline = ScoringPipeline(scorer_configs)
    result = await pipeline.run(
        input_text=job_data["input_text"],
        output_text=job_data["output_text"],
        reference=job_data.get("reference_text"),
    )

    # Persist to database
    async with async_session_factory() as session:
        record = ScoreResultModel(
            pipeline_id=job_data["pipeline_id"],
            trace_id=job_data["trace_id"],
            input_text=job_data["input_text"],
            output_text=job_data["output_text"],
            reference_text=job_data.get("reference_text"),
            aggregate_score=result.aggregate_score,
            individual_scores=[s.model_dump() for s in result.individual_scores],
        )
        session.add(record)
        await session.commit()

    # Submit to observability
    observability = get_observability_backend()
    for score in result.individual_scores:
        await observability.score(
            trace_id=job_data["trace_id"],
            name=score.name,
            value=score.value,
            comment=score.comment,
        )
    await observability.flush()

    logger.info(
        "scored_trace",
        trace_id=job_data["trace_id"],
        aggregate_score=result.aggregate_score,
    )


async def _handle_job_with_retry(redis: aioredis.Redis, job_json: str) -> None:
    """Process a job with retry logic and dead-letter queue."""
    job_data = json.loads(job_json)
    retry_count = job_data.get("_retry_count", 0)

    start = time.perf_counter()
    try:
        await process_job(job_data)
        SCORING_JOBS_TOTAL.labels(status="success").inc()
        SCORING_JOB_LATENCY.observe(time.perf_counter() - start)
    except Exception:
        SCORING_JOBS_TOTAL.labels(status="error").inc()

        if retry_count < MAX_RETRIES:
            retry_count += 1
            backoff = BASE_BACKOFF_SECONDS * (2 ** (retry_count - 1))
            logger.warning(
                "scoring_job_retry",
                trace_id=job_data.get("trace_id"),
                retry_count=retry_count,
                backoff_seconds=backoff,
            )
            WORKER_RETRY_COUNT.labels(worker_type="scoring").inc()
            await asyncio.sleep(backoff)
            job_data["_retry_count"] = retry_count
            await redis.lpush(SCORING_QUEUE, json.dumps(job_data))  # type: ignore[misc]
        else:
            logger.error(
                "scoring_job_dlq",
                trace_id=job_data.get("trace_id"),
                retry_count=retry_count,
            )
            WORKER_DLQ_COUNT.labels(worker_type="scoring").inc()
            await redis.lpush(SCORING_DLQ, json.dumps(job_data))  # type: ignore[misc]


_shutdown = False


async def run_worker() -> None:
    """Main worker loop — blocks waiting for scoring jobs."""
    global _shutdown

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown)

    logger.info("scoring_worker_started", queue=SCORING_QUEUE)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        while not _shutdown:
            result = await redis.brpop(SCORING_QUEUE, timeout=5)  # type: ignore[misc]
            if result is None:
                continue

            _, job_json = result
            await _handle_job_with_retry(redis, job_json)
    finally:
        await redis.aclose()
        logger.info("scoring_worker_stopped")


def _request_shutdown() -> None:
    global _shutdown
    logger.info("shutdown_signal_received", worker="scoring")
    _shutdown = True


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_worker())
