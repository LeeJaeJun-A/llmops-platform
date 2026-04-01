"""Parameter space utilities — generate variants from a parameter space."""

import itertools
import random
import uuid
from typing import Any

from llmops.core.tuning.base import ParameterRange, ParameterSet, ParameterSpace


def _expand_range(param: ParameterRange) -> list[Any]:
    """Expand a parameter range into discrete values."""
    if param.type == "categorical" and param.values:
        return param.values

    if param.type == "discrete" and param.values:
        return param.values

    if param.type == "continuous" and param.min_value is not None and param.max_value is not None:
        step = param.step or (param.max_value - param.min_value) / 5
        values = []
        v = param.min_value
        while v <= param.max_value:
            values.append(round(v, 6))
            v += step
        return values

    return []


def generate_grid_variants(space: ParameterSpace) -> list[ParameterSet]:
    """Generate all combinations (grid search) from a parameter space."""
    param_names = [p.name for p in space.parameters]
    param_values = [_expand_range(p) for p in space.parameters]

    variants = []
    for combo in itertools.product(*param_values):
        values = dict(zip(param_names, combo))
        variants.append(
            ParameterSet(
                variant_id=f"variant-{uuid.uuid4().hex[:8]}",
                values=values,
            )
        )
    return variants


def generate_random_variants(space: ParameterSpace, count: int = 5) -> list[ParameterSet]:
    """Generate random variants from a parameter space."""
    variants = []
    for _ in range(count):
        values: dict[str, Any] = {}
        for param in space.parameters:
            if param.type == "categorical" and param.values:
                values[param.name] = random.choice(param.values)
            elif (
                param.type == "continuous"
                and param.min_value is not None
                and param.max_value is not None
            ):
                values[param.name] = round(random.uniform(param.min_value, param.max_value), 4)
            elif param.values:
                values[param.name] = random.choice(param.values)

        variants.append(
            ParameterSet(
                variant_id=f"variant-{uuid.uuid4().hex[:8]}",
                values=values,
            )
        )
    return variants
