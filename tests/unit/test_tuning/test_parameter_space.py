from llmops.core.tuning.base import ParameterRange, ParameterSpace
from llmops.core.tuning.parameter_space import generate_grid_variants, generate_random_variants


def test_grid_categorical():
    space = ParameterSpace(
        parameters=[
            ParameterRange(name="model", type="categorical", values=["claude", "gemini"]),
            ParameterRange(name="temp", type="categorical", values=[0.3, 0.7, 1.0]),
        ]
    )
    variants = generate_grid_variants(space)
    # 2 models * 3 temps = 6 variants
    assert len(variants) == 6

    # Check all combinations exist
    combos = {(v.values["model"], v.values["temp"]) for v in variants}
    assert ("claude", 0.3) in combos
    assert ("gemini", 1.0) in combos


def test_grid_continuous_with_step():
    space = ParameterSpace(
        parameters=[
            ParameterRange(name="temp", type="continuous", min_value=0.0, max_value=1.0, step=0.5),
        ]
    )
    variants = generate_grid_variants(space)
    # 0.0, 0.5, 1.0 = 3 variants
    assert len(variants) == 3
    temps = sorted(v.values["temp"] for v in variants)
    assert temps == [0.0, 0.5, 1.0]


def test_random_variants_count():
    space = ParameterSpace(
        parameters=[
            ParameterRange(name="temp", type="continuous", min_value=0.0, max_value=1.0),
        ]
    )
    variants = generate_random_variants(space, count=10)
    assert len(variants) == 10
    for v in variants:
        assert 0.0 <= v.values["temp"] <= 1.0


def test_random_categorical():
    space = ParameterSpace(
        parameters=[
            ParameterRange(name="model", type="categorical", values=["a", "b", "c"]),
        ]
    )
    variants = generate_random_variants(space, count=20)
    models = {v.values["model"] for v in variants}
    # With 20 samples from 3 options, all should appear
    assert len(models) == 3


def test_grid_empty_space():
    space = ParameterSpace(parameters=[])
    variants = generate_grid_variants(space)
    # itertools.product of no iterables yields one empty tuple
    assert len(variants) == 1
    assert variants[0].values == {}
