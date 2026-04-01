from llmops.core.scoring.base import ScorerConfig
from llmops.core.scoring.pipeline import ScoringPipeline


async def test_pipeline_with_rule_based():
    configs = [
        ScorerConfig(
            strategy="rule_based",
            weight=1.0,
            config={"rules": [{"type": "min_length", "min": 5}]},
        ),
    ]
    pipeline = ScoringPipeline(configs)
    result = await pipeline.run(
        input_text="hi",
        output_text="hello world this is a test",
    )
    assert result.aggregate_score == 1.0
    assert len(result.individual_scores) == 1


async def test_pipeline_weighted_aggregate():
    configs = [
        ScorerConfig(
            strategy="rule_based",
            weight=0.6,
            config={"rules": [{"type": "min_length", "min": 5}]},
        ),
        ScorerConfig(
            strategy="embedding",
            weight=0.4,
            config={},
        ),
    ]
    pipeline = ScoringPipeline(configs)
    result = await pipeline.run(
        input_text="hi",
        output_text="hello world this is a test",
        reference="hello world this is a test",
    )
    # rule_based: 1.0, embedding: 1.0 (identical texts)
    # weighted: 0.6 * 1.0 + 0.4 * 1.0 = 1.0
    assert result.aggregate_score == 1.0
    assert len(result.individual_scores) == 2


async def test_pipeline_empty_scorers():
    pipeline = ScoringPipeline([])
    result = await pipeline.run(
        input_text="hi",
        output_text="hello",
    )
    assert result.aggregate_score == 0.0
    assert len(result.individual_scores) == 0
