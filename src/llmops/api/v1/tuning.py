"""Tuning/experiment API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.api.schemas.tuning import (
    ConcludeRequest,
    CreateExperimentRequest,
    ExperimentResponse,
    ExperimentResultsResponse,
    RecordTrialRequest,
    VariantResultResponse,
)
from llmops.core.tuning.base import (
    AllocationStrategy,
    ExperimentConfig,
    ParameterRange,
    ParameterSet,
    ParameterSpace,
)
from llmops.core.tuning.experiment import ExperimentRunner
from llmops.dependencies import get_db

router = APIRouter(prefix="/v1/tuning", tags=["tuning"])


def _get_runner(db: AsyncSession = Depends(get_db)) -> ExperimentRunner:
    return ExperimentRunner(db)


@router.post("/experiments", status_code=201)
async def create_experiment(
    req: CreateExperimentRequest,
    runner: ExperimentRunner = Depends(_get_runner),
) -> ExperimentResponse:
    """Create a new experiment."""
    try:
        param_ranges = [
            ParameterRange(**p.model_dump())
            for p in req.parameter_space.get("parameters", [])
        ]
        variants = [
            ParameterSet(variant_id=v.variant_id, values=v.values)
            for v in req.variants
        ]

        config = ExperimentConfig(
            name=req.name,
            description=req.description,
            parameter_space=ParameterSpace(parameters=param_ranges),
            scoring_pipeline_id=req.scoring_pipeline_id,
            allocation_strategy=AllocationStrategy(req.allocation_strategy),
            traffic_percentage=req.traffic_percentage,
            variants=variants,
        )
        result = await runner.create(config)
        return ExperimentResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/experiments")
async def list_experiments(
    runner: ExperimentRunner = Depends(_get_runner),
) -> list[ExperimentResponse]:
    """List all experiments."""
    results = await runner.list_experiments()
    return [ExperimentResponse(**r) for r in results]


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    runner: ExperimentRunner = Depends(_get_runner),
) -> ExperimentResponse:
    """Get an experiment by ID."""
    try:
        result = await runner.get(experiment_id)
        return ExperimentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(
    experiment_id: str,
    runner: ExperimentRunner = Depends(_get_runner),
) -> ExperimentResponse:
    """Start a draft experiment (move to RUNNING)."""
    try:
        result = await runner.start(experiment_id)
        return ExperimentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/experiments/{experiment_id}/allocate")
async def allocate_variant(
    experiment_id: str,
    key: str,
    runner: ExperimentRunner = Depends(_get_runner),
) -> dict:
    """Allocate a variant for a given key (user_id, request_id, etc.)."""
    try:
        variant = await runner.allocate_variant(experiment_id, key)
        if variant is None:
            return {"variant": None, "message": "Not allocated (outside traffic or not running)"}
        return {"variant": variant.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/experiments/{experiment_id}/trials")
async def record_trial(
    experiment_id: str,
    req: RecordTrialRequest,
    runner: ExperimentRunner = Depends(_get_runner),
) -> dict:
    """Record a trial result for an experiment."""
    try:
        result = await runner.record_trial(
            experiment_id,
            variant_id=req.variant_id,
            trace_id=req.trace_id,
            parameters=req.parameters,
            input_text=req.input_text,
            output_text=req.output_text,
            score=req.score,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/experiments/{experiment_id}/results")
async def get_results(
    experiment_id: str,
    runner: ExperimentRunner = Depends(_get_runner),
) -> ExperimentResultsResponse:
    """Get aggregated results for an experiment."""
    try:
        results = await runner.get_results(experiment_id)
        return ExperimentResultsResponse(
            id=results["id"],
            name=results["name"],
            status=results["status"],
            total_trials=results["total_trials"],
            results=[
                VariantResultResponse(
                    variant_id=r["variant_id"],
                    parameters=r["parameters"],
                    sample_count=r["sample_count"],
                    avg_score=r["avg_score"],
                    min_score=r["min_score"],
                    max_score=r["max_score"],
                )
                for r in results["results"]
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/experiments/{experiment_id}/conclude")
async def conclude_experiment(
    experiment_id: str,
    req: ConcludeRequest,
    runner: ExperimentRunner = Depends(_get_runner),
) -> ExperimentResponse:
    """Conclude an experiment, optionally specifying the winner."""
    try:
        result = await runner.conclude(experiment_id, winner_variant_id=req.winner_variant_id)
        return ExperimentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/experiments/{experiment_id}/cancel")
async def cancel_experiment(
    experiment_id: str,
    runner: ExperimentRunner = Depends(_get_runner),
) -> ExperimentResponse:
    """Cancel an experiment."""
    try:
        result = await runner.cancel(experiment_id)
        return ExperimentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
