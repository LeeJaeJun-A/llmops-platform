import pytest

from llmops.core.scoring.strategies.embedding import EmbeddingSimilarityScorer


@pytest.fixture
def scorer():
    return EmbeddingSimilarityScorer()


async def test_no_reference(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="hello world",
    )
    assert result.value == 0.0
    assert "No reference" in result.comment


async def test_identical_texts(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="the quick brown fox jumps",
        reference="the quick brown fox jumps",
    )
    assert result.value == 1.0


async def test_similar_texts(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="the quick brown fox jumps over the lazy dog",
        reference="the quick brown fox leaps over the lazy dog",
    )
    assert result.value > 0.8


async def test_different_texts(scorer):
    result = await scorer.score(
        input_text="hi",
        output_text="python programming language",
        reference="japanese sushi restaurant menu",
    )
    assert result.value < 0.3
