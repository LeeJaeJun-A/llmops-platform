"""Background tuning worker — aggregates experiment results periodically."""

import asyncio
import signal

from sqlalchemy import select

from llmops.core.tuning.base import ExperimentStatus
from llmops.core.tuning.experiment import ExperimentRunner
from llmops.db.models.experiment import ExperimentModel
from llmops.db.session import async_session_factory
from llmops.logging import get_logger, setup_logging

logger = get_logger(__name__)

POLL_INTERVAL = 30  # seconds
MAX_CHECK_RETRIES = 3
BASE_BACKOFF_SECONDS = 5.0


async def check_running_experiments() -> None:
    """Check all running experiments and log their current state."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ExperimentModel).where(
                ExperimentModel.status == ExperimentStatus.RUNNING.value
            )
        )
        experiments = result.scalars().all()

        runner = ExperimentRunner(session)
        for exp in experiments:
            retries = 0
            while retries <= MAX_CHECK_RETRIES:
                try:
                    results = await runner.get_results(str(exp.id))
                    total = results["total_trials"]
                    variant_count = len(results["results"])
                    logger.info(
                        "experiment_status",
                        experiment=exp.name,
                        total_trials=total,
                        variant_count=variant_count,
                    )
                    if results["results"]:
                        best = results["results"][0]
                        logger.info(
                            "experiment_leader",
                            experiment=exp.name,
                            variant=best["variant_id"],
                            avg_score=best["avg_score"],
                            sample_count=best["sample_count"],
                        )
                    break
                except Exception:
                    retries += 1
                    if retries > MAX_CHECK_RETRIES:
                        logger.exception(
                            "experiment_check_failed",
                            experiment=exp.name,
                            retries=retries,
                        )
                    else:
                        backoff = BASE_BACKOFF_SECONDS * (2 ** (retries - 1))
                        logger.warning(
                            "experiment_check_retry",
                            experiment=exp.name,
                            retry=retries,
                            backoff_seconds=backoff,
                        )
                        await asyncio.sleep(backoff)


_shutdown = False


async def run_worker() -> None:
    """Main worker loop — periodically checks running experiments."""
    global _shutdown

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown)

    logger.info("tuning_worker_started", poll_interval=POLL_INTERVAL)

    while not _shutdown:
        try:
            await check_running_experiments()
        except Exception:
            logger.exception("tuning_worker_error")

        # Sleep in small increments to respond to shutdown quickly
        for _ in range(POLL_INTERVAL):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("tuning_worker_stopped")


def _request_shutdown() -> None:
    global _shutdown
    logger.info("shutdown_signal_received", worker="tuning")
    _shutdown = True


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_worker())
