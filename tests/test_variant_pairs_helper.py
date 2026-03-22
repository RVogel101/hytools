"""Tests for variant pairs helper (moved from WesternArmenianLLM)."""

import json

from hytool.linguistics.dialect.variant_pairs_helper import (
    build_starter_variant_pairs,
    save_variant_pairs_json,
)


def test_build_starter_variant_pairs_ranks_and_filters():
    mapping = {
        "ea_low": {
            "canonical_western_form": "wa_low",
            "canonical_western_frequency_in_wa": 1,
            "eastern_frequency_in_wa": 0,
            "canonical_western_dominance_ratio": 1.0,
            "canonical_frequency_delta": 1,
        },
        "ea_high": {
            "canonical_western_form": "wa_high",
            "canonical_western_frequency_in_wa": 50,
            "eastern_frequency_in_wa": 5,
            "canonical_western_dominance_ratio": 50 / 55,
            "canonical_frequency_delta": 45,
        },
        "ea_reject_delta": {
            "canonical_western_form": "wa_reject_delta",
            "canonical_western_frequency_in_wa": 2,
            "eastern_frequency_in_wa": 4,
            "canonical_western_dominance_ratio": 2 / 6,
            "canonical_frequency_delta": -2,
        },
    }

    pairs = build_starter_variant_pairs(
        mapping,
        top_k=10,
        min_support=2,
        min_dominance=0.5,
        min_frequency_delta=1,
    )

    assert pairs == [("wa_high", "ea_high")]


def test_save_variant_pairs_json_format(tmp_path):
    out_file = tmp_path / "variant_pairs.json"
    save_variant_pairs_json([("wa1", "ea1"), ("wa2", "ea2")], out_file)

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload == [["wa1", "ea1"], ["wa2", "ea2"]]

