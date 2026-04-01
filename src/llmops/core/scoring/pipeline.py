"""Scoring pipeline — orchestrates multiple scorers with weights."""

import asyncio
from typing import Any

from llmops.core.scoring.base import (
    PipelineResult,
    Scorer,
    ScorerConfig,
)
from llmops.core.scoring.registry import get_scorer


class ScoringPipeline:
    """Runs multiple scorers in parallel, returns weighted aggregate."""

    def __init__(self, scorer_configs: list[ScorerConfig]) -> None:
        self._configs = scorer_configs
        self._scorers: list[tuple[Scorer, float, dict[str, Any]]] = []

        total_weight = sum(c.weight for c in scorer_configs)
        for sc in scorer_configs:
            scorer = get_scorer(sc.strategy)
            normalized_weight = sc.weight / total_weight if total_weight > 0 else 0
            self._scorers.append((scorer, normalized_weight, sc.config))

    async def run(
        self,
        *,
        input_text: str,
        output_text: str,
        reference: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Run all scorers in parallel and return aggregated result."""
        tasks = [
            scorer.score(
                input_text=input_text,
                output_text=output_text,
                reference=reference,
                context=context,
                config=config,
            )
            for scorer, _, config in self._scorers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        individual_scores = []
        weighted_sum = 0.0

        for (_, weight, _), result in zip(self._scorers, results):
            if isinstance(result, BaseException):
                continue
            individual_scores.append(result)
            weighted_sum += result.value * weight

        return PipelineResult(
            individual_scores=individual_scores,
            aggregate_score=round(weighted_sum, 4),
        )
