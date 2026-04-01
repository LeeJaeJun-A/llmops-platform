"""Scoring engine base abstractions."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScoreDataType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


class ScoreResult(BaseModel):
    """Result from a single scorer."""

    name: str
    value: float
    data_type: ScoreDataType = ScoreDataType.NUMERIC
    comment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineResult(BaseModel):
    """Aggregated result from a scoring pipeline."""

    individual_scores: list[ScoreResult]
    aggregate_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScorerConfig(BaseModel):
    """Configuration for a scorer within a pipeline."""

    strategy: str
    weight: float = 1.0
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """Configuration for a scoring pipeline."""

    name: str
    description: str = ""
    scorers: list[ScorerConfig]


class Scorer(ABC):
    """Abstract base for a single scoring strategy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this scoring strategy."""
        ...

    @abstractmethod
    async def score(
        self,
        *,
        input_text: str,
        output_text: str,
        reference: str | None = None,
        context: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> ScoreResult:
        """Score a single input/output pair."""
        ...
