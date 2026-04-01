"""Tuning engine base abstractions."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AllocationStrategy(str, Enum):
    AB_TEST = "ab_test"
    GRID = "grid"
    RANDOM = "random"


class ParameterRange(BaseModel):
    """Defines a single parameter's search space."""

    name: str
    type: str = "continuous"  # continuous, discrete, categorical
    min_value: float | None = None
    max_value: float | None = None
    values: list[Any] | None = None  # for categorical/discrete
    step: float | None = None  # for discrete


class ParameterSpace(BaseModel):
    """Defines the full parameter search space for an experiment."""

    parameters: list[ParameterRange]


class ParameterSet(BaseModel):
    """A specific set of parameter values (one variant)."""

    variant_id: str
    values: dict[str, Any] = Field(default_factory=dict)


class ExperimentConfig(BaseModel):
    """Configuration for creating an experiment."""

    name: str
    description: str = ""
    parameter_space: ParameterSpace
    scoring_pipeline_id: str | None = None
    allocation_strategy: AllocationStrategy = AllocationStrategy.AB_TEST
    traffic_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    variants: list[ParameterSet] = Field(default_factory=list)


class VariantResult(BaseModel):
    """Aggregated result for a single variant."""

    variant_id: str
    parameters: dict[str, Any]
    sample_count: int = 0
    avg_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    scores: list[float] = Field(default_factory=list)
