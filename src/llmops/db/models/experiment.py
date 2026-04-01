"""Database models for experiments and tuning."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from llmops.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExperimentModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An experiment defines a parameter tuning run."""

    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(50), default="draft", server_default="draft")
    allocation_strategy: Mapped[str] = mapped_column(
        String(50), default="ab_test", server_default="ab_test"
    )
    parameter_space: Mapped[dict] = mapped_column(JSON, nullable=False)
    variants: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    scoring_pipeline_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    traffic_percentage: Mapped[float] = mapped_column(Float, default=100.0, server_default="100.0")
    winner_variant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentTrialModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single trial (request) within an experiment."""

    __tablename__ = "experiment_trials"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
