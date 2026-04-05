import argparse

from hytools.ingestion.runner import (
    _build_parser,
    _build_stages,
    _collect_stage_transition_notices,
    _run_stage,
    _stage_enabled,
    _stage_groups,
    run_pipeline,
)


def _subparsers(parser: argparse.ArgumentParser):
    return next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )


def test_runner_command_surface_is_pinned():
    parser = _build_parser()
    commands = set(_subparsers(parser).choices)

    assert commands == {"run", "status", "list", "dashboard", "doctor", "schedule", "release"}


def test_run_group_choices_are_pinned():
    parser = _build_parser()
    run_parser = _subparsers(parser).choices["run"]
    group_action = next(
        action for action in run_parser._actions if "--group" in action.option_strings
    )

    assert set(group_action.choices) == {"all", "scraping", "extraction", "postprocessing"}


def test_scraping_group_matches_current_stage_registry():
    expected = [
        "wikipedia",
        "wikisource",
        "archive_org",
        "hathitrust",
        "gallica",
        "loc",
        "dpla",
        "news",
        "web_crawler",
        "culturax",
        "opus",
        "jw",
        "english_sources",
        "nayiri",
        "gomidas",
        "mechitarist",
        "agbu",
        "hamazkayin",
        "agos",
        "ocr_ingest",
        "mss_nkr",
        "worldcat_searcher",
    ]

    assert _stage_groups({})["scraping"] == expected


def test_scraping_group_stays_in_sync_with_acquisition_modules():
    acquisition_stage_names = [
        stage.name
        for stage in _build_stages({})
        if stage.module.startswith("hytools.ingestion.acquisition.")
        or stage.module.startswith("hytools.ingestion.discovery.")
    ]

    assert _stage_groups({})["scraping"] == acquisition_stage_names


def test_explicit_opt_in_stages_default_disabled_until_configured():
    cfg = {"scraping": {}, "ingestion": {}, "_meta": {"explicit_scraping_keys": [], "explicit_ingestion_keys": []}}

    assert _stage_enabled(cfg, "wikipedia") is True
    assert _stage_enabled(cfg, "web_crawler") is False
    assert _stage_enabled(cfg, "incremental_merge") is False
    assert _stage_enabled(cfg, "corpus_export") is False


def test_explicit_stage_config_overrides_transition_default():
    cfg = {
        "scraping": {"web_crawler": {"enabled": True}},
        "ingestion": {"corpus_export": {"enabled": True}},
        "_meta": {
            "explicit_scraping_keys": ["web_crawler"],
            "explicit_ingestion_keys": ["corpus_export"],
        },
    }

    assert _stage_enabled(cfg, "web_crawler") is True
    assert _stage_enabled(cfg, "corpus_export") is True


def test_stage_enablement_uses_correct_config_section_for_scraping_stage():
    cfg = {
        "scraping": {"dpla": {"enabled": False}},
        "ingestion": {"dpla": {"enabled": True}},
        "_meta": {
            "explicit_scraping_keys": ["dpla"],
            "explicit_ingestion_keys": [],
        },
    }

    assert _stage_enabled(cfg, "dpla") is False


def test_transition_notices_distinguish_implicit_and_explicit_opt_in_stages():
    notices = {
        notice["stage_key"]: notice
        for notice in _collect_stage_transition_notices(
            {"scraping": {}, "ingestion": {}, "_meta": {"explicit_scraping_keys": [], "explicit_ingestion_keys": []}}
        )
    }

    assert notices["wikipedia"]["code"] == "implicit-stage-enable"
    assert notices["wikipedia"]["default_enabled"] is True
    assert notices["web_crawler"]["code"] == "explicit-opt-in-stage"
    assert notices["web_crawler"]["default_enabled"] is False


def test_run_parser_accepts_dry_run_flag():
    parser = _build_parser()

    args = parser.parse_args(["run", "--dry-run"])

    assert args.dry_run is True


def test_list_parser_accepts_config_flag():
    parser = _build_parser()

    args = parser.parse_args(["list", "--config", "config/settings.yaml"])

    assert str(args.config).endswith("settings.yaml")


def test_run_pipeline_dry_run_does_not_execute_stage(monkeypatch):
    calls: list[str] = []

    def _boom(stage, cfg):
        calls.append(stage.name)
        raise AssertionError("dry-run should not execute stages")

    monkeypatch.setattr("hytools.ingestion.runner._run_stage", _boom)

    summary = run_pipeline(
        {"paths": {"log_dir": "data/logs"}, "scraping": {}, "ingestion": {}, "_meta": {"explicit_scraping_keys": [], "explicit_ingestion_keys": []}},
        only=["wikipedia"],
        dry_run=True,
    )

    assert summary["dry_run"] is True
    assert any(stage["stage"] == "wikipedia" and stage["status"] == "planned" for stage in summary["stages"])
    assert calls == []