from __future__ import annotations

import json
from pathlib import Path

from hytools.ingestion.aggregation import corpus_export
from hytools.ingestion.doctor import format_doctor_report, run_doctor


def test_doctor_reports_missing_paths_placeholder_secrets_and_transition_notices(tmp_path, monkeypatch):
    for relative in ["data", "data/raw", "data/cleaned", "data/filtered", "data/logs", "data/metadata", "cache"]:
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("hytools.ingestion.doctor._module_available", lambda _name: True)

    config_path = tmp_path / "config" / "settings.yaml"
    config = {
        "_meta": {"config_path": str(config_path), "validation_mode": "pydantic"},
        "paths": {
            "data_root": "data",
            "raw_dir": "data/raw",
            "cleaned_dir": "data/cleaned",
            "filtered_dir": "data/filtered",
            "log_dir": "data/logs",
            "metadata_dir": "data/metadata",
            "cache_dir": "cache",
        },
        "database": {"use_mongodb": False},
        "scraping": {
            "dpla": {"enabled": True, "api_key": "DPLA_API_KEY"},
            "culturax": {"enabled": False},
            "web_crawler": {
                "enabled": True,
                "seed_file": "data/retrieval/crawler_seeds.txt",
                "discovery_report": "data/retrieval/crawler_found.csv",
                "audit_report_csv": "data/retrieval/wa_crawler_audit.csv",
                "audit_report_json": "data/retrieval/wa_crawler_audit.json",
                "search_seeding": {"enabled": False},
                "playwright_fallback": {"enabled": False},
            },
        },
        "export": {
            "formats": [],
            "release": {"include_huggingface": False, "include_full_parquet": False, "include_dataset_card": False, "include_checksums": False},
        },
        "scheduler": {},
    }

    report = run_doctor(
        config,
        config_path=config_path,
        transition_notices=[
            {
                "level": "warning",
                "code": "implicit-stage-enable",
                "message": "Stage 'wikipedia' is not explicitly configured and still defaults to enabled during the transition.",
                "setting": "scraping.wikipedia.enabled",
                "fix": "Set scraping.wikipedia.enabled explicitly to true or false.",
                "stage_key": "wikipedia",
                "default_enabled": True,
            }
        ],
    )

    error_codes = {issue.code for issue in report.errors}
    warning_codes = {issue.code for issue in report.warnings}
    rendered = format_doctor_report(report)

    assert "missing-path" in error_codes
    assert "placeholder-secret" in error_codes
    assert "missing-dpla-api-key" in error_codes
    assert "implicit-stage-enable" in warning_codes
    assert "scraping.web_crawler.seed_file" in rendered
    assert "scraping.dpla.api_key" in rendered


def test_doctor_ignores_placeholder_secret_for_disabled_stage(tmp_path, monkeypatch):
    for relative in ["data", "data/raw", "data/cleaned", "data/filtered", "data/logs", "data/metadata", "cache"]:
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("hytools.ingestion.doctor._module_available", lambda _name: True)

    config_path = tmp_path / "config" / "settings.yaml"
    config = {
        "_meta": {"config_path": str(config_path), "validation_mode": "pydantic"},
        "paths": {
            "data_root": "data",
            "raw_dir": "data/raw",
            "cleaned_dir": "data/cleaned",
            "filtered_dir": "data/filtered",
            "log_dir": "data/logs",
            "metadata_dir": "data/metadata",
            "cache_dir": "cache",
        },
        "database": {"use_mongodb": False},
        "scraping": {
            "dpla": {"enabled": False, "api_key": ""},
            "culturax": {"enabled": False},
            "web_crawler": {
                "enabled": False,
                "search_seeding": {"enabled": False},
                "playwright_fallback": {"enabled": False},
            },
        },
        "export": {
            "formats": [],
            "release": {"include_huggingface": False, "include_full_parquet": False, "include_dataset_card": False, "include_checksums": False},
        },
        "scheduler": {},
    }

    report = run_doctor(config, config_path=config_path, transition_notices=[])

    error_codes = {issue.code for issue in report.errors}
    assert "placeholder-secret" not in error_codes
    assert "missing-dpla-api-key" not in error_codes


def test_build_release_writes_deterministic_artifacts(tmp_path, monkeypatch):
    rows = [
        {"id": "1", "content_hash": "aaa", "normalized_content_hash": "aaa", "source": "alpha", "text": "one"},
        {"id": "2", "content_hash": "bbb", "normalized_content_hash": "bbb", "source": "alpha", "text": "two"},
        {"id": "3", "content_hash": "ccc", "normalized_content_hash": "ccc", "source": "beta", "text": "three"},
        {"id": "4", "content_hash": "ddd", "normalized_content_hash": "ddd", "source": "gamma", "text": "four"},
    ]

    def fake_iter_documents(_config, _dialect_filter=None):
        return iter(rows)

    def fake_write_parquet(split_rows, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(list(split_rows), sort_keys=True, ensure_ascii=False), encoding="utf-8")

    def fake_write_huggingface(split_rows, output_path: Path):
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "dataset.json").write_text(
            json.dumps(list(split_rows), sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    monkeypatch.setattr(corpus_export, "_iter_documents", fake_iter_documents)
    monkeypatch.setattr(corpus_export, "_write_parquet_rows", fake_write_parquet)
    monkeypatch.setattr(corpus_export, "_write_huggingface_rows", fake_write_huggingface)
    monkeypatch.setattr(corpus_export, "_utcnow_iso", lambda: "2026-01-01T00:00:00+00:00")

    config = {
        "export": {
            "release": {
                "dataset_name": "hytools-test-release",
                "dataset_version": "1.2.3",
                "split_seed": "stable-seed",
                "train_ratio": 0.5,
                "validation_ratio": 0.25,
                "test_ratio": 0.25,
                "include_huggingface": True,
                "include_full_parquet": True,
                "include_dataset_card": True,
                "include_checksums": True,
            }
        }
    }

    first_root = tmp_path / "release-a"
    second_root = tmp_path / "release-b"
    first = corpus_export.build_release(config, output_path=first_root)
    second = corpus_export.build_release(config, output_path=second_root)

    first_manifest = json.loads((first_root / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second_root / "manifest.json").read_text(encoding="utf-8"))
    first_checksums = (first_root / "SHA256SUMS.txt").read_text(encoding="utf-8")

    assert first["split_counts"] == second["split_counts"]
    assert first_manifest["split_counts"] == second_manifest["split_counts"]
    assert first_manifest["source_counts"] == {"alpha": 2, "beta": 1, "gamma": 1}
    assert (first_root / "splits" / "train.parquet").read_text(encoding="utf-8") == (second_root / "splits" / "train.parquet").read_text(encoding="utf-8")
    assert (first_root / "splits" / "validation.parquet").read_text(encoding="utf-8") == (second_root / "splits" / "validation.parquet").read_text(encoding="utf-8")
    assert (first_root / "splits" / "test.parquet").read_text(encoding="utf-8") == (second_root / "splits" / "test.parquet").read_text(encoding="utf-8")
    assert (first_root / "README.md").exists()
    assert (first_root / "huggingface" / "train" / "dataset.json").exists()
    assert "manifest.json" in first_checksums
    assert "huggingface/train" in first_checksums
    assert {artifact["type"] for artifact in first["artifacts"]} >= {"parquet-split", "parquet-full", "huggingface-split", "manifest", "dataset-card", "checksums"}