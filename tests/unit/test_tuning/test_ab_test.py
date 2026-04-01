from llmops.core.tuning.ab_test import ABTestAllocator
from llmops.core.tuning.base import ParameterSet


def _make_variants(n: int) -> list[ParameterSet]:
    return [
        ParameterSet(variant_id=f"v{i}", values={"temp": 0.1 * (i + 1)})
        for i in range(n)
    ]


def test_allocate_deterministic():
    """Same key always gets the same variant."""
    variants = _make_variants(3)
    allocator = ABTestAllocator(variants)

    v1 = allocator.allocate("user-123")
    v2 = allocator.allocate("user-123")
    assert v1 is not None
    assert v1.variant_id == v2.variant_id


def test_allocate_different_keys_distribute():
    """Different keys should spread across variants."""
    variants = _make_variants(3)
    allocator = ABTestAllocator(variants)

    assigned = set()
    for i in range(100):
        v = allocator.allocate(f"user-{i}")
        if v:
            assigned.add(v.variant_id)

    # With 100 users and 3 variants, all should be represented
    assert len(assigned) == 3


def test_allocate_traffic_zero():
    """0% traffic means no one gets allocated."""
    variants = _make_variants(2)
    allocator = ABTestAllocator(variants, traffic_percentage=0.0)

    results = [allocator.allocate(f"user-{i}") for i in range(50)]
    assert all(r is None for r in results)


def test_allocate_traffic_partial():
    """With 50% traffic, roughly half should get allocated."""
    variants = _make_variants(2)
    allocator = ABTestAllocator(variants, traffic_percentage=50.0)

    allocated = sum(1 for i in range(1000) if allocator.allocate(f"user-{i}") is not None)
    # Should be roughly 500, allow wide margin
    assert 300 < allocated < 700


def test_allocate_empty_variants():
    allocator = ABTestAllocator([], traffic_percentage=100.0)
    assert allocator.allocate("user-1") is None


def test_variant_count():
    variants = _make_variants(5)
    allocator = ABTestAllocator(variants)
    assert allocator.variant_count == 5
