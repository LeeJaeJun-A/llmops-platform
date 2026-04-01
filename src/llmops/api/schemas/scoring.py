"""API schemas for scoring endpoints."""

from typing import Any

from pydantic import BaseModel, Field

# --- Pipeline CRUD ---

class ScorerConfigRequest(BaseModel):
    strategy: str
    weight: float = 1.0
    config: dict[str, Any] = Field(default_factory=dict)


class CreatePipelineRequest(BaseModel):
    name: str
    description: str = ""
    scorers: list[ScorerConfigRequest]


class PipelineResponse(BaseModel):
    id: str
    name: str
    description: str
    scorers: list[ScorerConfigRequest]
    is_active: bool
    created_at: str


class PipelineListResponse(BaseModel):
    pipelines: list[PipelineResponse]


# --- Scoring Trigger ---

class EvaluateRequest(BaseModel):
    trace_id: str
    pipeline_id: str
    input_text: str
    output_text: str
    reference_text: str | None = None


class ScoreResultResponse(BaseModel):
    name: str
    value: float
    comment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    trace_id: str
    pipeline_id: str
    aggregate_score: float
    individual_scores: list[ScoreResultResponse]


# --- Query Results ---

class ScoreResultsQueryResponse(BaseModel):
    trace_id: str
    results: list[EvaluateResponse]
