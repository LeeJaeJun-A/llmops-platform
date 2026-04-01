"""initial schema

Revision ID: 6bb66dd772ba
Revises:
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6bb66dd772ba"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_now = sa.func.now()
_tz = sa.DateTime(timezone=True)


def _id_col() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "id", sa.Uuid(), nullable=False,
        default=sa.text("gen_random_uuid()"),
    )


def _ts_cols() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", _tz, server_default=_now, nullable=False),
        sa.Column("updated_at", _tz, server_default=_now, nullable=False),
    ]


def upgrade() -> None:
    # --- prompts ---
    op.create_table(
        "prompts",
        _id_col(),
        *_ts_cols(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompts_name", "prompts", ["name"], unique=True)

    # --- prompt_versions ---
    op.create_table(
        "prompt_versions",
        _id_col(),
        *_ts_cols(),
        sa.Column("prompt_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column(
            "environment",
            sa.Enum("draft", "staging", "production", name="promptenvironment"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("variables", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("change_note", sa.Text(), server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["prompt_id"], ["prompts.id"], ondelete="CASCADE",
        ),
        sa.UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )

    # --- scoring_pipelines ---
    op.create_table(
        "scoring_pipelines",
        _id_col(),
        *_ts_cols(),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("scorers_config", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- score_results ---
    op.create_table(
        "score_results",
        _id_col(),
        *_ts_cols(),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("aggregate_score", sa.Float(), nullable=False),
        sa.Column("individual_scores", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["scoring_pipelines.id"]),
    )
    op.create_index(
        "ix_score_results_trace_id", "score_results", ["trace_id"],
    )

    # --- experiments ---
    op.create_table(
        "experiments",
        _id_col(),
        *_ts_cols(),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("status", sa.String(50), server_default="draft", nullable=False),
        sa.Column(
            "allocation_strategy", sa.String(50),
            server_default="ab_test", nullable=False,
        ),
        sa.Column("parameter_space", sa.JSON(), nullable=False),
        sa.Column("variants", sa.JSON(), nullable=False),
        sa.Column("scoring_pipeline_id", sa.String(255), nullable=True),
        sa.Column(
            "traffic_percentage", sa.Float(),
            server_default="100.0", nullable=False,
        ),
        sa.Column("winner_variant_id", sa.String(255), nullable=True),
        sa.Column("concluded_at", _tz, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- experiment_trials ---
    op.create_table(
        "experiment_trials",
        _id_col(),
        *_ts_cols(),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.String(255), nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), server_default=""),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_experiment_trials_experiment_id",
        "experiment_trials", ["experiment_id"],
    )
    op.create_index(
        "ix_experiment_trials_variant_id",
        "experiment_trials", ["variant_id"],
    )


def downgrade() -> None:
    op.drop_table("experiment_trials")
    op.drop_table("experiments")
    op.drop_table("score_results")
    op.drop_table("scoring_pipelines")
    op.drop_table("prompt_versions")
    op.drop_table("prompts")
    op.execute("DROP TYPE IF EXISTS promptenvironment")
