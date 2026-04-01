"""Composite scorer — wraps a ScoringPipeline as a single Scorer for nesting."""

from typing import Any

from llmops.core.scoring.base import Scorer, ScorerConfig, ScoreResult


class CompositeScorer(Scorer):
    """A scorer that runs a nested pipeline of other scorers.

    Config options:
    - scorers: list of ScorerConfig dicts [{"strategy": "...", "weight": ..., "config": {...}}]
    """

    @property
    def name(self) -> str:
        return "composite"

    async def score(
        self,
        *,
        input_text: str,
        output_text: str,
        reference: str | None = None,
        context: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> ScoreResult:
        config = config or {}
        scorer_dicts = config.get("scorers", [])

        if not scorer_dicts:
            return ScoreResult(
                name=self.name,
                value=0.0,
                comment="No sub-scorers configured in composite",
            )

        # Import here to avoid circular dependency at module level
        from llmops.core.scoring.pipeline import ScoringPipeline

        scorer_configs = [
            ScorerConfig(
                strategy=s["strategy"],
                weight=s.get("weight", 1.0),
                config=s.get("config", {}),
            )
            for s in scorer_dicts
        ]

        pipeline = ScoringPipeline(scorer_configs)
        result = await pipeline.run(
            input_text=input_text,
            output_text=output_text,
            reference=reference,
            context=context,
        )

        return ScoreResult(
            name=self.name,
            value=result.aggregate_score,
            comment=f"Composite of {len(scorer_configs)} scorers",
            metadata={
                "sub_scores": [s.model_dump() for s in result.individual_scores],
            },
        )
