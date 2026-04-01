"""API schemas for tuning/experiment endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class ParameterRangeRequest(BaseModel):
    name: str
    type: str = "continuous"
    min_value: float | None = None
    max_value: float | None = None
    values: list[Any] | None = None
    step: float | None = None


class VariantRequest(BaseModel):
    variant_id: str
    values: dict[str, Any] = Field(default_factory=dict)


class CreateExperimentRequest(BaseModel):
    name: str
    description: str = ""
    parameter_space: dict[str, list[ParameterRangeRequest]]
    scoring_pipeline_id: str | None = None
    allocation_strategy: str = "ab_test"
    traffic_percentage: float = 100.0
    variants: list[VariantRequest] = Field(default_factory=list)


class RecordTrialRequest(BaseModel):
    variant_id: str
    trace_id: str
    parameters: dict[str, Any]
    input_text: str
    output_text: str
    score: float | None = None


class ConcludeRequest(BaseModel):
    winner_variant_id: str | None = None


class ExperimentResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    allocation_strategy: str
    parameter_space: dict[str, Any]
    variants: list[dict[str, Any]]
    scoring_pipeline_id: str | None
    traffic_percentage: float
    winner_variant_id: str | None
    concluded_at: str | None
    created_at: str


class VariantResultResponse(BaseModel):
    variant_id: str
    parameters: dict[str, Any]
    sample_count: int
    avg_score: float
    min_score: float
    max_score: float


class ExperimentResultsResponse(BaseModel):
    id: str
    name: str
    status: str
    results: list[VariantResultResponse]
    total_trials: int
