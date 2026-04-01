"""A/B test allocator — assigns incoming requests to experiment variants."""

import hashlib

from llmops.core.tuning.base import ParameterSet


class ABTestAllocator:
    """Deterministic variant assignment based on a key (user_id, request_id, etc.).

    Uses consistent hashing so the same key always gets the same variant.
    """

    def __init__(self, variants: list[ParameterSet], traffic_percentage: float = 100.0) -> None:
        self._variants = variants
        self._traffic_percentage = traffic_percentage

    def allocate(self, key: str) -> ParameterSet | None:
        """Assign a variant to the given key.

        Returns None if the request falls outside the traffic percentage.
        """
        if not self._variants:
            return None

        # Use hash to deterministically decide if this key is in the experiment
        hash_int = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        bucket = hash_int % 10000  # 0-9999 for 0.01% granularity

        threshold = int(self._traffic_percentage * 100)  # e.g., 50% -> 5000
        if bucket >= threshold:
            return None  # Outside traffic percentage

        # Assign to a variant
        variant_idx = hash_int % len(self._variants)
        return self._variants[variant_idx]

    @property
    def variant_count(self) -> int:
        return len(self._variants)
