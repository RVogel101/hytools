from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_pipeline as run_pipeline


def _args(**overrides):
    defaults = {
        "stage": "all",
        "config": Path("config/settings.yaml"),
        "dry_run": False,
        "only_runner_stage": [],
        "skip_runner_stage": [],
        "pdf": None,
        "overwrite": False,
        "output": "data/cleaned_corpus",
        "source_collection": "documents",
        "output_collection": "documents_cleaned",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_build_execution_plan_includes_runner_substages():
    plan = run_pipeline._build_execution_plan(_args(), {})

    assert [step["name"] for step in plan] == ["scrape", "ocr", "clean", "ingest"]
    assert "archive_org" in plan[0]["runner_stages"]
    assert "metadata_tagger" in plan[3]["runner_stages"]


def test_build_execution_plan_applies_runner_filters_and_drops_empty_all_steps():
    plan = run_pipeline._build_execution_plan(
        _args(stage="all", only_runner_stage=["archive_org"]),
        {},
    )

    assert [step["name"] for step in plan] == ["scrape", "ocr", "clean"]
    assert plan[0]["runner_stages"] == ["archive_org"]


def test_build_execution_plan_rejects_empty_explicit_runner_stage_selection():
    with pytest.raises(ValueError, match="No runner stages remain"):
        run_pipeline._build_execution_plan(
            _args(stage="ingest", only_runner_stage=["archive_org"]),
            {},
        )


def test_validate_args_rejects_runner_filters_for_ocr_only():
    with pytest.raises(ValueError, match="only apply"):
        run_pipeline._validate_args(_args(stage="ocr", only_runner_stage=["archive_org"]))


def test_validate_args_rejects_pdf_outside_ocr():
    with pytest.raises(ValueError, match="--pdf is only valid"):
        run_pipeline._validate_args(_args(stage="scrape", pdf=Path("sample.pdf")))