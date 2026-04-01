"""Scorer registry — maps strategy names to scorer instances."""

from llmops.core.scoring.base import Scorer

_registry: dict[str, type[Scorer]] = {}


def register_scorer(name: str, scorer_cls: type[Scorer]) -> None:
    _registry[name] = scorer_cls


def get_scorer(name: str) -> Scorer:
    if name not in _registry:
        available = list(_registry.keys())
        raise ValueError(
            f"Unknown scoring strategy '{name}'. Available: {available}"
        )
    return _registry[name]()


def list_scorers() -> list[str]:
    return list(_registry.keys())


def _register_defaults() -> None:
    """Register built-in scoring strategies."""
    from llmops.core.scoring.strategies.composite import CompositeScorer
    from llmops.core.scoring.strategies.embedding import EmbeddingSimilarityScorer
    from llmops.core.scoring.strategies.llm_judge import LLMJudgeScorer
    from llmops.core.scoring.strategies.rule_based import RuleBasedScorer

    register_scorer("rule_based", RuleBasedScorer)
    register_scorer("llm_judge", LLMJudgeScorer)
    register_scorer("embedding", EmbeddingSimilarityScorer)
    register_scorer("composite", CompositeScorer)


_register_defaults()
