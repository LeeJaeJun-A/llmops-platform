"""Scoring API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.api.middleware.rate_limit import rate_limit_dependency
from llmops.api.schemas.scoring import (
    CreatePipelineRequest,
    EvaluateRequest,
    EvaluateResponse,
    PipelineListResponse,
    PipelineResponse,
    ScorerConfigRequest,
    ScoreResultResponse,
)
from llmops.core.observability.base import ObservabilityBackend
from llmops.core.scoring.base import ScorerConfig
from llmops.core.scoring.pipeline import ScoringPipeline
from llmops.core.scoring.registry import list_scorers
from llmops.db.models.score import ScoreResultModel, ScoringPipelineModel
from llmops.dependencies import get_db, get_observability_backend

router = APIRouter(
    prefix="/v1/scoring",
    tags=["scoring"],
    dependencies=[Depends(rate_limit_dependency)],
)


def _pipeline_to_response(p: ScoringPipelineModel) -> PipelineResponse:
    scorers = [
        ScorerConfigRequest(
            strategy=s["strategy"],
            weight=s.get("weight", 1.0),
            config=s.get("config", {}),
        )
        for s in p.scorers_config
    ]
    return PipelineResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        scorers=scorers,
        is_active=p.is_active,
        created_at=p.created_at.isoformat(),
    )


@router.get("/strategies")
async def list_strategies() -> dict[str, list[str]]:
    """List available scoring strategies."""
    return {"strategies": list_scorers()}


@router.post("/pipelines", status_code=201)
async def create_pipeline(
    req: CreatePipelineRequest,
    db: AsyncSession = Depends(get_db),
) -> PipelineResponse:
    """Create a new scoring pipeline configuration."""
    # Validate all strategies exist
    available = list_scorers()
    for s in req.scorers:
        if s.strategy not in available:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy '{s.strategy}'. Available: {available}",
            )

    pipeline = ScoringPipelineModel(
        name=req.name,
        description=req.description,
        scorers_config=[s.model_dump() for s in req.scorers],
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    return _pipeline_to_response(pipeline)


@router.get("/pipelines")
async def list_pipelines(
    db: AsyncSession = Depends(get_db),
) -> PipelineListResponse:
    """List all scoring pipelines."""
    result = await db.execute(
        select(ScoringPipelineModel).where(ScoringPipelineModel.is_active.is_(True))
    )
    pipelines = result.scalars().all()
    return PipelineListResponse(pipelines=[_pipeline_to_response(p) for p in pipelines])


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> PipelineResponse:
    """Get a specific scoring pipeline."""
    result = await db.execute(
        select(ScoringPipelineModel).where(ScoringPipelineModel.id == pipeline_id)
    )
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return _pipeline_to_response(pipeline)


@router.post("/evaluate")
async def evaluate(
    req: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
    observability: ObservabilityBackend = Depends(get_observability_backend),
) -> EvaluateResponse:
    """Run a scoring pipeline on given input/output."""
    # Load pipeline config
    result = await db.execute(
        select(ScoringPipelineModel).where(ScoringPipelineModel.id == req.pipeline_id)
    )
    pipeline_model = result.scalar_one_or_none()
    if not pipeline_model:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Build and run pipeline
    scorer_configs = [
        ScorerConfig(
            strategy=s["strategy"],
            weight=s.get("weight", 1.0),
            config=s.get("config", {}),
        )
        for s in pipeline_model.scorers_config
    ]
    pipeline = ScoringPipeline(scorer_configs)
    pipeline_result = await pipeline.run(
        input_text=req.input_text,
        output_text=req.output_text,
        reference=req.reference_text,
    )

    # Persist result
    score_record = ScoreResultModel(
        pipeline_id=pipeline_model.id,
        trace_id=req.trace_id,
        input_text=req.input_text,
        output_text=req.output_text,
        reference_text=req.reference_text,
        aggregate_score=pipeline_result.aggregate_score,
        individual_scores=[s.model_dump() for s in pipeline_result.individual_scores],
    )
    db.add(score_record)
    await db.commit()

    # Submit scores to observability backend
    for score in pipeline_result.individual_scores:
        await observability.score(
            trace_id=req.trace_id,
            name=score.name,
            value=score.value,
            comment=score.comment,
        )
    await observability.score(
        trace_id=req.trace_id,
        name="aggregate",
        value=pipeline_result.aggregate_score,
        comment=f"Pipeline: {pipeline_model.name}",
    )

    return EvaluateResponse(
        trace_id=req.trace_id,
        pipeline_id=str(pipeline_model.id),
        aggregate_score=pipeline_result.aggregate_score,
        individual_scores=[
            ScoreResultResponse(
                name=s.name,
                value=s.value,
                comment=s.comment,
                metadata=s.metadata,
            )
            for s in pipeline_result.individual_scores
        ],
    )


@router.get("/results/{trace_id}")
async def get_results(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get scoring results for a trace."""
    result = await db.execute(select(ScoreResultModel).where(ScoreResultModel.trace_id == trace_id))
    records = result.scalars().all()

    return {
        "trace_id": trace_id,
        "results": [
            {
                "pipeline_id": str(r.pipeline_id),
                "aggregate_score": r.aggregate_score,
                "individual_scores": r.individual_scores,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }
