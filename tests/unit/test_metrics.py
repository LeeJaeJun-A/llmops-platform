"""Tests for Prometheus metrics module."""

from llmops.metrics import _normalize_path


def test_normalize_path_simple():
    assert _normalize_path("/v1/chat/completions") == "/v1/chat/completions"


def test_normalize_path_with_uuid():
    path = "/v1/scoring/pipelines/550e8400-e29b-41d4-a716-446655440000"
    assert _normalize_path(path) == "/v1/scoring/pipelines/{id}"


def test_normalize_path_with_numeric_id():
    assert _normalize_path("/v1/prompts/123") == "/v1/prompts/{id}"


def test_normalize_path_preserves_non_id_segments():
    assert _normalize_path("/v1/tuning/experiments") == "/v1/tuning/experiments"


def test_normalize_path_multiple_ids():
    path = "/v1/experiments/550e8400-e29b-41d4-a716-446655440000/trials/123"
    assert _normalize_path(path) == "/v1/experiments/{id}/trials/{id}"


def test_normalize_path_root():
    assert _normalize_path("/") == "/"


def test_normalize_healthz():
    assert _normalize_path("/healthz") == "/healthz"
