"""Database models for prompt management."""

from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from llmops.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PromptEnvironment(str, PyEnum):
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"


class PromptModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A prompt is a named entity with multiple versions."""

    __tablename__ = "prompts"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    versions: Mapped[list["PromptVersionModel"]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersionModel.version.desc()",
    )


class PromptVersionModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable versioned prompt template."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )

    prompt_id: Mapped["UUID"] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[PromptEnvironment] = mapped_column(
        Enum(PromptEnvironment, values_callable=lambda e: [x.value for x in e]),
        default=PromptEnvironment.DRAFT,
        server_default="draft",
        nullable=False,
    )
    variables: Mapped[dict] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False,
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, server_default="{}")
    change_note: Mapped[str] = mapped_column(Text, default="", server_default="")

    prompt: Mapped[PromptModel] = relationship(back_populates="versions")
