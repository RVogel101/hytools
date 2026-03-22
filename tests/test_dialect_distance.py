"""Tests for dialect distance module (moved from WesternArmenianLLM)."""

from collections import Counter

from hytool.linguistics.dialect.dialect_distance import (
    DistanceWeights,
    compute_component_distance,
    cosine_distance,
    hellinger_distance,
    jensen_shannon_divergence,
    wasserstein_1d,
    weighted_jaccard_distance,
)


def test_distribution_distances_identity_zero():
    p = {"a": 0.5, "b": 0.5}
    q = {"a": 0.5, "b": 0.5}

    assert jensen_shannon_divergence(p, q) == 0.0
    assert hellinger_distance(p, q) == 0.0
    assert cosine_distance(p, q) == 0.0


def test_weighted_jaccard_reasonable_range():
    a = Counter({"x": 10, "y": 2})
    b = Counter({"x": 5, "z": 5})
    d = weighted_jaccard_distance(a, b)
    assert 0.0 <= d <= 1.0


def test_wasserstein_1d_zero_for_same_samples():
    vals = [4, 5, 6, 7]
    assert wasserstein_1d(vals, vals) == 0.0


def test_component_distance_returns_expected_fields():
    west = [
        "alpha beta alpha beta.",
        "alpha beta gamma.",
    ]
    east = [
        "delta epsilon delta.",
        "delta epsilon zeta.",
    ]

    mapping = {
        "delta": {
            "canonical_western_form": "alpha",
            "canonical_western_frequency_in_wa": 100,
        }
    }

    report = compute_component_distance(
        western_texts=west,
        eastern_texts=east,
        west_east_mapping=mapping,
        variant_pairs=[("alpha", "delta")],
        function_words={"alpha", "beta", "delta", "epsilon"},
    )

    assert 0.0 <= report.lexical_component <= 1.0
    assert 0.0 <= report.structural_component <= 1.0
    assert 0.0 <= report.total_distance <= 1.0

    assert "js_divergence" in report.lexical_metrics
    assert "weighted_jaccard_distance" in report.lexical_metrics
    assert "mapping_shift_rate" in report.lexical_metrics
    assert "variant_usage_rate_distance" in report.lexical_metrics
    assert "sentence_length_wasserstein" in report.structural_metrics
    assert "function_bigram_js" in report.structural_metrics


def test_component_distance_weight_override():
    west = ["alpha alpha beta."]
    east = ["gamma gamma delta."]

    weights = DistanceWeights(
        lexical_weight=1.0,
        structural_weight=0.0,
        lexical_subweights={
            "js_divergence": 1.0,
            "weighted_jaccard_distance": 0.0,
            "mapping_shift_rate": 0.0,
        },
        structural_subweights={
            "sentence_length_wasserstein": 1.0,
            "function_bigram_js": 0.0,
        },
    )

    report = compute_component_distance(west, east, weights=weights)
    assert abs(report.total_distance - report.lexical_metrics["js_divergence"]) < 1e-9

