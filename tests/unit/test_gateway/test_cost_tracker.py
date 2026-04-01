from llmops.core.gateway.cost_tracker import estimate_cost


def test_estimate_cost_known_model():
    # claude-sonnet-4: $3/M input, $15/M output
    cost = estimate_cost("claude-sonnet-4-20250514", input_tokens=1000, output_tokens=500)
    expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
    assert abs(cost - expected) < 1e-6


def test_estimate_cost_gemini():
    # gemini-2.0-flash: $0.10/M input, $0.40/M output
    cost = estimate_cost("gemini-2.0-flash", input_tokens=10000, output_tokens=5000)
    expected = (10000 / 1_000_000) * 0.10 + (5000 / 1_000_000) * 0.40
    assert abs(cost - expected) < 1e-6


def test_estimate_cost_unknown_model():
    # Falls back to $1/M input, $3/M output
    cost = estimate_cost("unknown-model", input_tokens=1_000_000, output_tokens=1_000_000)
    expected = 1.0 + 3.0
    assert abs(cost - expected) < 1e-6


def test_estimate_cost_zero_tokens():
    cost = estimate_cost("claude-sonnet-4-20250514", input_tokens=0, output_tokens=0)
    assert cost == 0.0
