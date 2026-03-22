"""Tests for dialect pair orthographic load metric extraction (moved from WesternArmenianLLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hytool.linguistics.dialect.dialect_pair_metrics import (
    compute_dialect_pair_metrics,
    load_pairs,
    save_records_jsonl,
    save_summary_json,
    summarize_records,
)


def test_compute_pair_metrics_counts_and_deltas():
    pairs = [
        ("բերեցի", "բերել ես", None, None),
    ]

    records = compute_dialect_pair_metrics(pairs, alpha=1.0, beta=2.0)
    assert len(records) == 1

    r = records[0]
    assert r.western_letter_count == len("բերեցի")
    assert r.eastern_letter_count == len("բերելես")
    assert r.western_space_count == 0
    assert r.eastern_space_count == 1

    assert r.letter_delta == (len("բերելես") - len("բերեցի"))
    assert r.space_delta == 1
    assert r.orthographic_load == r.letter_delta + 2.0 * r.space_delta


def test_load_pairs_accepts_list_and_mapping_formats(tmp_path: Path):
    list_path = tmp_path / "pairs_list.json"
    list_path.write_text(
        json.dumps([["խօսիլ", "խոսել"], ["կ'ըսեմ", "կասեմ"]], ensure_ascii=False),
        encoding="utf-8",
    )

    loaded_list = load_pairs(list_path)
    assert len(loaded_list) == 2
    assert loaded_list[0][0] == "խօսիլ"
    assert loaded_list[0][1] == "խոսել"

    mapping_path = tmp_path / "pairs_mapping.json"
    mapping_payload = {
        "խոսել": {
            "canonical_western_form": "խօսիլ",
            "confidence": 0.93,
        },
        "գալ": {
            "canonical_western_form": "գալ",
        },
    }
    mapping_path.write_text(
        json.dumps(mapping_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded_mapping = load_pairs(mapping_path)
    assert len(loaded_mapping) == 2
    assert loaded_mapping[0][0] == "խօսիլ"
    assert loaded_mapping[0][1] == "խոսել"
    assert loaded_mapping[0][2] == 0.93
    assert loaded_mapping[0][3] == "west_east_usage_mapping"


def test_summarize_records_outputs_percentages():
    pairs = [
        ("aaa", "aaaa", None, None),  # +1 letter
        ("x y", "xy", None, None),    # -1 space
        ("same", "same", None, None),
    ]
    records = compute_dialect_pair_metrics(pairs)
    summary = summarize_records(records)

    assert summary.total_pairs == 3
    assert summary.pct_eastern_more_letters == pytest.approx((1 / 3) * 100, abs=1e-4)
    assert summary.pct_equal_letter_count == pytest.approx((2 / 3) * 100, abs=1e-4)


def test_save_outputs(tmp_path: Path):
    pairs = [("ab", "abc", None, "test")]
    records = compute_dialect_pair_metrics(pairs)
    summary = summarize_records(records)

    jsonl_path = save_records_jsonl(records, tmp_path / "dialect_pair_metrics.jsonl")
    summary_path = save_summary_json(summary, tmp_path / "dialect_load_summary.json")

    assert jsonl_path.exists()
    assert summary_path.exists()

    jsonl_lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl_lines) == 1
    row = json.loads(jsonl_lines[0])
    assert row["western_form"] == "ab"
    assert row["eastern_form"] == "abc"

    summary_obj = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_obj["total_pairs"] == 1

