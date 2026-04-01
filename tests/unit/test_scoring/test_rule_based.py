import pytest

from llmops.core.scoring.strategies.rule_based import RuleBasedScorer


@pytest.fixture
def scorer():
    return RuleBasedScorer()


async def test_no_rules_returns_perfect(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="hello world",
        config={},
    )
    assert result.value == 1.0


async def test_min_length_pass(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="hello world, this is a long response",
        config={"rules": [{"type": "min_length", "min": 10}]},
    )
    assert result.value == 1.0


async def test_min_length_fail(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="short",
        config={"rules": [{"type": "min_length", "min": 100}]},
    )
    assert result.value == 0.0


async def test_contains_keywords(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="Hello World, how are you?",
        config={"rules": [{"type": "contains", "keywords": ["hello", "world"]}]},
    )
    assert result.value == 1.0


async def test_not_contains(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="Everything is fine",
        config={"rules": [{"type": "not_contains", "keywords": ["error", "fail"]}]},
    )
    assert result.value == 1.0


async def test_json_valid(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text='{"key": "value"}',
        config={"rules": [{"type": "json_valid"}]},
    )
    assert result.value == 1.0


async def test_json_invalid(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="not json",
        config={"rules": [{"type": "json_valid"}]},
    )
    assert result.value == 0.0


async def test_regex_match(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="The date is 2024-01-15",
        config={"rules": [{"type": "regex_match", "pattern": r"\d{4}-\d{2}-\d{2}"}]},
    )
    assert result.value == 1.0


async def test_multiple_rules_partial(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="short",
        config={
            "rules": [
                {"type": "min_length", "min": 100},  # fail
                {"type": "contains", "keywords": ["short"]},  # pass
            ]
        },
    )
    assert result.value == 0.5
