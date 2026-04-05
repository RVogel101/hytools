from __future__ import annotations

from argparse import Namespace

from hytools.ingestion import research_runner


def test_apply_cli_research_overrides_updates_config_values():
    cfg = {
        "research": {
            "exclude_dirs": ["augmented"],
            "exclude_sources": ["augmented"],
            "metadata_patterns": ["*.json"],
            "error_threshold_pct": 10.0,
        }
    }
    args = Namespace(
        exclude_dirs=["logs", "cache"],
        exclude_sources=["augmented", "ocr_ingest"],
        metadata_patterns=["*.jsonl"],
        error_threshold_pct=5.0,
    )

    updated = research_runner._apply_cli_research_overrides(cfg, args)

    assert updated["research"] == {
        "exclude_dirs": ["logs", "cache"],
        "exclude_sources": ["augmented", "ocr_ingest"],
        "metadata_patterns": ["*.jsonl"],
        "error_threshold_pct": 5.0,
    }


def test_build_parser_accepts_research_override_flags():
    parser = research_runner._build_parser()

    args = parser.parse_args(
        [
            "--exclude-dirs",
            "logs",
            "cache",
            "--exclude-sources",
            "augmented",
            "rss_news",
            "--metadata-patterns",
            "*.json",
            "*.jsonl",
            "--error-threshold-pct",
            "7.5",
        ]
    )

    assert args.exclude_dirs == ["logs", "cache"]
    assert args.exclude_sources == ["augmented", "rss_news"]
    assert args.metadata_patterns == ["*.json", "*.jsonl"]
    assert args.error_threshold_pct == 7.5