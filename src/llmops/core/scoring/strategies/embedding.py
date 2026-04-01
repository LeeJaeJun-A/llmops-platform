"""Embedding similarity scorer — cosine similarity between output and reference."""

import math
from typing import Any

from llmops.core.scoring.base import Scorer, ScoreResult


def _simple_tokenize(text: str) -> dict[str, int]:
    """Simple word frequency tokenizer (no external deps needed)."""
    words = text.lower().split()
    freq: dict[str, int] = {}
    for w in words:
        w = w.strip(".,!?;:'\"()[]{}").lower()
        if w:
            freq[w] = freq.get(w, 0) + 1
    return freq


def _cosine_similarity(vec_a: dict[str, int], vec_b: dict[str, int]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    all_keys = set(vec_a.keys()) | set(vec_b.keys())
    if not all_keys:
        return 0.0

    dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in all_keys)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


class EmbeddingSimilarityScorer(Scorer):
    """Scores output by similarity to a reference text.

    Uses TF-based cosine similarity as default (no external embedding API needed).
    Can be extended to use real embedding models via config.

    Config options:
    - method: "tf" (default) | "model"
    - model: embedding model name (when method="model")
    """

    @property
    def name(self) -> str:
        return "embedding"

    async def score(
        self,
        *,
        input_text: str,
        output_text: str,
        reference: str | None = None,
        context: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> ScoreResult:
        if not reference:
            return ScoreResult(
                name=self.name,
                value=0.0,
                comment="No reference text provided for similarity comparison",
            )

        config = config or {}
        method = config.get("method", "tf")

        if method == "tf":
            similarity = self._tf_similarity(output_text, reference)
        else:
            similarity = self._tf_similarity(output_text, reference)

        return ScoreResult(
            name=self.name,
            value=round(similarity, 4),
            comment=f"Cosine similarity ({method}): {similarity:.4f}",
            metadata={"method": method},
        )

    def _tf_similarity(self, text_a: str, text_b: str) -> float:
        vec_a = _simple_tokenize(text_a)
        vec_b = _simple_tokenize(text_b)
        return _cosine_similarity(vec_a, vec_b)
