from __future__ import annotations

from pathlib import Path

from hytools.linguistics.dialect.review_audit import (
    get_review_priority,
    get_stage_review_settings,
    load_review_audit_config,
)


def test_review_audit_config_is_centralized_in_linguistics_directory():
    config = load_review_audit_config()
    heuristics_file = (
        Path(__file__).resolve().parents[1]
        / "hytools"
        / "linguistics"
        / "dialect"
        / "review_heuristics.yaml"
    )

    assert heuristics_file.exists()
    assert "default" in config
    assert "stages" in config
    assert "priority_mapping" in config


def test_stage_review_settings_merge_stage_defaults_and_overrides():
    settings = get_stage_review_settings("web_crawler", {"confidence_threshold": 0.5})

    assert settings["queue_source"] == "crawler"
    assert settings["confidence_threshold"] == 0.5
    assert settings["score_margin_threshold"] == 2.0
    assert settings["min_armenian_ratio"] == 0.05


def test_review_priority_comes_from_centralized_mapping():
    assert get_review_priority("low_confidence_dialect_classification", 99) == 1
    assert get_review_priority("source_policy_exception", 99) == 2
    assert get_review_priority("unknown_reason", 7) == 7