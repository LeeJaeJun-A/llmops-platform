"""Database models for scoring pipelines and results."""

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from llmops.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScoringPipelineModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scoring_pipelines"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    scorers_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    results: Mapped[list["ScoreResultModel"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )


class ScoreResultModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "score_results"

    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scoring_pipelines.id"),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    aggregate_score: Mapped[float] = mapped_column(Float, nullable=False)
    individual_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    pipeline: Mapped[ScoringPipelineModel] = relationship(back_populates="results")
