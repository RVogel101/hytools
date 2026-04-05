"""Unified ingestion pipeline runner — acquisition + extraction + enrichment + aggregation.

Runs every data-acquisition and processing stage in sequence with per-stage
error isolation, optional background mode, and a machine-readable summary.

Usage
-----
Run everything::

    python -m hytools.ingestion.runner run

Run in background::

    python -m hytools.ingestion.runner run --background

Run only selected stages::

    python -m hytools.ingestion.runner run --only wikipedia archive_org

Skip stages::

    python -m hytools.ingestion.runner run --skip news gallica

Check last summary::

    python -m hytools.ingestion.runner status
"""

from __future__ import annotations

import argparse
import html
import importlib
import inspect
import json
import logging
import os
import subprocess
import sys
import time
from urllib.parse import quote_plus
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hytools.config.settings import ValidationError as SettingsValidationError, load_config

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("config") / "settings.yaml"
_DEFAULT_LOG_DIR = Path("data") / "logs"
_PID_FILENAME = ".pipeline_runner.pid"
_SUMMARY_FILENAME = "pipeline_summary.json"
_DASHBOARD_DETAIL_SUFFIX = "_details"
_EXPLICIT_OPT_IN_STAGE_KEYS = frozenset(
    {
        "web_crawler",
        "worldcat",
        "incremental_merge",
        "word_frequency_facets",
        "drift_detection",
        "export_corpus_overlap_fingerprints",
        "corpus_export",
    }
)
_SCRAPING_STAGE_KEYS = frozenset(
    {
        "wikipedia",
        "wikisource",
        "archive_org",
        "hathitrust",
        "gallica",
        "loc",
        "dpla",
        "newspapers",
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
        "worldcat",
        "eastern_armenian",
        "rss_news",
    }
)
_REGISTERED_STAGE_KEYS = (
    "wikipedia",
    "wikisource",
    "archive_org",
    "hathitrust",
    "gallica",
    "loc",
    "dpla",
    "newspapers",
    "eastern_armenian",
    "rss_news",
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
    "worldcat",
    "cleaning",
    "metadata_tagger",
    "frequency_aggregator",
    "incremental_merge",
    "word_frequency_facets",
    "drift_detection",
    "export_corpus_overlap_fingerprints",
    "corpus_export",
    "extraction",
)


@dataclass
class Stage:
    name: str
    module: str
    enabled: bool = True
    group: str | None = None
    has_run: bool = True
    has_main: bool = False
    supports_mongodb: bool = False
    entry_point: str | None = None  # if set, call this instead of run() (e.g. ingestion.acquisition.wiki: run_wikipedia / run_wikisource)


def _stage_config_value(cfg: dict, key: str):
    section = "scraping" if key in _SCRAPING_STAGE_KEYS else "ingestion"
    return (cfg.get(section) or {}).get(key)


def _explicit_stage_keys(cfg: dict) -> set[str]:
    meta = cfg.get("_meta", {}) or {}
    return set(meta.get("explicit_scraping_keys", [])) | set(meta.get("explicit_ingestion_keys", []))


def _stage_flag_from_value(value) -> bool:
    if isinstance(value, dict):
        return bool(value.get("enabled", True))
    if value is None:
        return True
    return bool(value)


def _config_setting_name(stage_key: str) -> str:
    section = "scraping" if stage_key in _SCRAPING_STAGE_KEYS else "ingestion"
    return f"{section}.{stage_key}.enabled"


def _stage_enabled(cfg: dict, key: str) -> bool:
    if key in _explicit_stage_keys(cfg):
        return _stage_flag_from_value(_stage_config_value(cfg, key))
    if key in _EXPLICIT_OPT_IN_STAGE_KEYS:
        return False
    return _stage_flag_from_value(_stage_config_value(cfg, key))


def _collect_stage_transition_notices(cfg: dict) -> list[dict]:
    explicit = _explicit_stage_keys(cfg)
    notices: list[dict] = []
    for key in _REGISTERED_STAGE_KEYS:
        if key in explicit:
            continue
        setting = _config_setting_name(key)
        if key in _EXPLICIT_OPT_IN_STAGE_KEYS:
            notices.append(
                {
                    "level": "warning",
                    "code": "explicit-opt-in-stage",
                    "setting": setting,
                    "message": f"Stage '{key}' is not explicitly configured and now defaults to disabled.",
                    "fix": f"Set {setting} to true to opt in.",
                    "stage_key": key,
                    "default_enabled": False,
                }
            )
        else:
            notices.append(
                {
                    "level": "warning",
                    "code": "implicit-stage-enable",
                    "setting": setting,
                    "message": f"Stage '{key}' is not explicitly configured and still defaults to enabled during the transition.",
                    "fix": f"Set {setting} explicitly to true or false.",
                    "stage_key": key,
                    "default_enabled": True,
                }
            )
    return notices


def _emit_stage_transition_notices(cfg: dict) -> None:
    for notice in _collect_stage_transition_notices(cfg):
        logger.warning("%s Fix: %s", notice["message"], notice["fix"])


def _load_runner_config(config_path: Path | None) -> tuple[dict, Path | None]:
    candidate = config_path
    if candidate is None:
        candidate = _DEFAULT_CONFIG_PATH if _DEFAULT_CONFIG_PATH.exists() else None

    if candidate is None:
        return _ensure_config({}), None

    if not candidate.exists():
        raise FileNotFoundError(f"Config file not found: {candidate}")

    return _ensure_config(load_config(str(candidate))), candidate


def _build_stages(cfg: dict) -> list[Stage]:
    """Build the complete ordered list of pipeline stages.

    Stages live under ingestion (acquisition, discovery, extraction, enrichment,
    aggregation, validation). Config is read from hytools.ingestion.* or scraping.* for backward compatibility.
    """
    return [
        # ── Acquisition: Wikimedia ────────────────────────────────────────
        Stage("wikipedia",       "hytools.ingestion.acquisition.wiki",            enabled=_stage_enabled(cfg, "wikipedia"),         group="scraping", supports_mongodb=True, entry_point="run_wikipedia"),
        Stage("wikisource",      "hytools.ingestion.acquisition.wiki",            enabled=_stage_enabled(cfg, "wikisource"),        group="scraping", supports_mongodb=True, entry_point="run_wikisource"),

        # ── Acquisition: Digital libraries ───────────────────────────────
        Stage("archive_org",     "hytools.ingestion.acquisition.archive_org",     enabled=_stage_enabled(cfg, "archive_org"),       group="scraping", supports_mongodb=True),
        Stage("hathitrust",      "hytools.ingestion.acquisition.hathitrust",      enabled=_stage_enabled(cfg, "hathitrust"),        group="scraping", supports_mongodb=True),
        Stage("gallica",         "hytools.ingestion.acquisition.gallica",         enabled=_stage_enabled(cfg, "gallica"),           group="scraping", supports_mongodb=True),
        Stage("loc",             "hytools.ingestion.acquisition.loc",             enabled=_stage_enabled(cfg, "loc"),               group="scraping", supports_mongodb=True),
        Stage("dpla",            "hytools.ingestion.acquisition.dpla",            enabled=_stage_enabled(cfg, "dpla"),              group="scraping", supports_mongodb=True),

        # ── Acquisition: News (diaspora newspapers + EA agencies + RSS) ───
        Stage("news",            "hytools.ingestion.acquisition.news",            enabled=_stage_enabled(cfg, "newspapers") or _stage_enabled(cfg, "eastern_armenian") or _stage_enabled(cfg, "rss_news"), group="scraping", supports_mongodb=True),
        Stage("web_crawler",     "hytools.ingestion.acquisition.web_crawler",     enabled=_stage_enabled(cfg, "web_crawler"),      group="scraping", supports_mongodb=True),

        # ── Acquisition: Datasets ────────────────────────────────────────
        Stage("culturax",        "hytools.ingestion.acquisition.culturax",        enabled=_stage_enabled(cfg, "culturax"),          group="scraping", supports_mongodb=True),
        Stage("opus",            "hytools.ingestion.acquisition.opus",            enabled=_stage_enabled(cfg, "opus"),              group="scraping", supports_mongodb=True),
        Stage("jw",              "hytools.ingestion.acquisition.jw",              enabled=_stage_enabled(cfg, "jw"),                group="scraping", supports_mongodb=True),
        Stage("english_sources", "hytools.ingestion.acquisition.english_sources",  enabled=_stage_enabled(cfg, "english_sources"),  group="scraping", supports_mongodb=True),

        # ── Acquisition: Reference ───────────────────────────────────────
        Stage("nayiri",          "hytools.ingestion.acquisition.nayiri",          enabled=_stage_enabled(cfg, "nayiri"),            group="scraping", supports_mongodb=True),
        Stage("gomidas",         "hytools.ingestion.acquisition.gomidas",         enabled=_stage_enabled(cfg, "gomidas"),          group="scraping", supports_mongodb=True),
        Stage("mechitarist",     "hytools.ingestion.acquisition.mechitarist",     enabled=_stage_enabled(cfg, "mechitarist"),      group="scraping", supports_mongodb=True),
        Stage("agbu",            "hytools.ingestion.acquisition.agbu",            enabled=_stage_enabled(cfg, "agbu"),             group="scraping", supports_mongodb=True),
        Stage("hamazkayin",      "hytools.ingestion.acquisition.hamazkayin",      enabled=_stage_enabled(cfg, "hamazkayin"),       group="scraping", supports_mongodb=True),
        Stage("agos",            "hytools.ingestion.acquisition.agos",            enabled=_stage_enabled(cfg, "agos"),             group="scraping", supports_mongodb=True),
        Stage("ocr_ingest",      "hytools.ingestion.acquisition.ocr_ingest",      enabled=_stage_enabled(cfg, "ocr_ingest"),       group="scraping", supports_mongodb=True),
        Stage("mss_nkr",         "hytools.ingestion.acquisition.mss_nkr",         enabled=_stage_enabled(cfg, "mss_nkr"),          group="scraping", supports_mongodb=True),
        Stage("worldcat_searcher", "hytools.ingestion.discovery.worldcat_searcher", enabled=_stage_enabled(cfg, "worldcat"),      group="scraping", has_run=True, has_main=True),

        # ── Post-processing ──────────────────────────────────────────────
          Stage("cleaning",              "hytools.cleaning.run_mongodb",           enabled=_stage_enabled(cfg, "cleaning"), group="postprocessing", has_run=True, has_main=False),
          Stage("metadata_tagger",       "hytools.ingestion.enrichment.metadata_tagger",       enabled=_stage_enabled(cfg, "metadata_tagger"), group="postprocessing"),
          Stage("frequency_aggregator",      "hytools.ingestion.aggregation.frequency_aggregator",      enabled=_stage_enabled(cfg, "frequency_aggregator"), group="postprocessing"),
          Stage("incremental_merge",        "hytools.ingestion.aggregation.incremental_merge",        enabled=_stage_enabled(cfg, "incremental_merge"), group="postprocessing"),
          Stage("word_frequency_facets",   "hytools.ingestion.aggregation.word_frequency_facets",   enabled=_stage_enabled(cfg, "word_frequency_facets"), group="postprocessing"),
          Stage("drift_detection",          "hytools.ingestion.aggregation.drift_detection",          enabled=_stage_enabled(cfg, "drift_detection"), group="postprocessing"),
          Stage("export_corpus_overlap_fingerprints", "hytools.ingestion.validation.export_corpus_overlap_fingerprints",
              enabled=_stage_enabled(cfg, "export_corpus_overlap_fingerprints"), group="postprocessing", has_run=True, has_main=True),
          Stage("corpus_export",             "hytools.ingestion.aggregation.corpus_export",
              enabled=_stage_enabled(cfg, "corpus_export"), group="postprocessing", has_run=True, has_main=True),

        # ── Extraction pipeline (all MongoDB-native) ────────────────────
          Stage("import_anki_to_mongodb",                "hytools.ingestion.extraction.import_anki_to_mongodb",
              enabled=_stage_enabled(cfg, "extraction"), group="extraction", has_run=True, has_main=True),
          Stage("validate_contract_alignment",           "hytools.ingestion.validation.validate_contract_alignment",
              enabled=_stage_enabled(cfg, "extraction"), group="extraction", has_run=True, has_main=True),
          Stage("materialize_dialect_views",             "hytools.ingestion.enrichment.materialize_dialect_views",
              enabled=_stage_enabled(cfg, "extraction"), group="extraction", has_run=True, has_main=False),
          Stage("summarize_unified_documents",           "hytools.ingestion.aggregation.summarize_unified_documents",
              enabled=_stage_enabled(cfg, "extraction"), group="extraction", has_run=True, has_main=False),
    ]


def _stage_groups(cfg: dict | None = None) -> dict[str, list[str]]:
    groups = {"scraping": [], "extraction": [], "postprocessing": []}
    for stage in _build_stages(cfg or {}):
        if stage.group in groups:
            groups[stage.group].append(stage.name)
    return groups


# ── Default config builders ─────────────────────────────────────────────────

def _default_database_config() -> dict:
    return {
        "use_mongodb": True,
        "mongodb_uri": "mongodb://localhost:27017/",
        "mongodb_database": "western_armenian_corpus",
    }


def _default_paths() -> dict:
    return {
        "raw_dir": "data/raw",
        "data_root": "data",
        "log_dir": "data/logs",
    }


def _default_ingestion_config() -> dict:
    return {
        "wikipedia": {"language": "hyw", "dump_date": "latest"},
        "wikisource": {"categories": ["Category:Armenian_literature", "Category:Western_Armenian"]},
        "archive_org": {},
        "mss_nkr": {},
        "culturax": {},
        "opus": {},
        "jw": {},
        "hathitrust": {},
        "gallica": {},
        "loc": {},
        "dpla": {},
        "web_crawler": {},
        "ocr_ingest": {},
        "gomidas": {},
        "mechitarist": {},
        "agbu": {},
        "hamazkayin": {},
        "agos": {},
        "newspapers": {},
        "nayiri": {},
        "eastern_armenian": {},
        "rss_news": {},
        "english_sources": {},
        "worldcat": {},
        "cleaning": {},
        "metadata_tagger": {},
        "frequency_aggregator": {},
        "incremental_merge": {},
        "word_frequency_facets": {},
        "drift_detection": {},
        "export_corpus_overlap_fingerprints": {},
        "corpus_export": {},
        "extraction": {},
    }


def _ensure_config(cfg: dict) -> dict:
    """Fill in missing config sections with sane defaults."""
    if "paths" not in cfg or not cfg["paths"]:
        cfg = {**cfg, "paths": _default_paths()}
    else:
        for k, v in _default_paths().items():
            cfg["paths"].setdefault(k, v)

    if "database" not in cfg or not cfg["database"]:
        cfg = {**cfg, "database": _default_database_config()}
    else:
        for k, v in _default_database_config().items():
            cfg["database"].setdefault(k, v)

    # Support both ingestion and scraping config keys for backward compatibility
    for key in ("ingestion", "scraping"):
        if key not in cfg or not cfg[key]:
            cfg = {**cfg, key: _default_ingestion_config()}
        else:
            for stage, defaults in _default_ingestion_config().items():
                if stage not in cfg[key]:
                    cfg[key][stage] = defaults
                elif isinstance(defaults, dict) and isinstance(cfg[key].get(stage), dict):
                    for k, v in defaults.items():
                        cfg[key][stage].setdefault(k, v)
    return cfg


# ── Stage execution ─────────────────────────────────────────────────────────

def _resolve_log_dir(cfg: dict) -> Path:
    paths = cfg.get("paths", {})
    log_dir = paths.get("log_dir")
    if log_dir:
        return Path(log_dir)
    data_root = paths.get("data_root")
    if data_root:
        return Path(data_root) / "logs"
    return _DEFAULT_LOG_DIR


def _write_pid(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / _PID_FILENAME).write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid(log_dir: Path) -> None:
    try:
        (log_dir / _PID_FILENAME).unlink(missing_ok=True)
    except OSError:
        pass


def _run_stage(stage: Stage, cfg: dict) -> dict:
    t0 = time.monotonic()
    rec: dict = {
        "stage": stage.name,
        "module": stage.module,
        "enabled": stage.enabled,
        "status": "skipped" if not stage.enabled else "pending",
        "duration_seconds": 0.0,
        "error": "",
    }
    if not stage.enabled:
        return rec

    try:
        mod = importlib.import_module(stage.module)
        run_fn = None
        if stage.entry_point and hasattr(mod, stage.entry_point):
            run_fn = getattr(mod, stage.entry_point)
        elif stage.has_run and hasattr(mod, "run"):
            run_fn = mod.run

        if run_fn is not None:
            logger.info("Running stage: %s", stage.name)
            sig = inspect.signature(run_fn)
            if len(sig.parameters) >= 1:
                run_fn(cfg)
            else:
                run_fn()
        elif stage.has_main and hasattr(mod, "main"):
            logger.info("Running stage: %s (main)", stage.name)
            result = mod.main()
            if isinstance(result, int) and result != 0:
                raise RuntimeError(f"main() returned exit code {result}")
        else:
            raise RuntimeError(f"Module {stage.module} has no run() or main()")

        rec["status"] = "ok"
    except Exception as exc:
        logger.exception("Stage failed: %s", stage.name)
        rec["status"] = "failed"
        rec["error"] = str(exc)
    finally:
        rec["duration_seconds"] = round(time.monotonic() - t0, 3)
    return rec


def _apply_stage_filters(
    stages: list[Stage],
    *,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> list[Stage]:
    only_set = set(only or [])
    skip_set = set(skip or [])

    if only_set:
        for st in stages:
            st.enabled = st.enabled and st.name in only_set
    if skip_set:
        for st in stages:
            st.enabled = st.enabled and st.name not in skip_set
    return stages


def _build_dry_run_records(stages: list[Stage]) -> list[dict]:
    records: list[dict] = []
    for stage in stages:
        records.append(
            {
                "stage": stage.name,
                "module": stage.module,
                "enabled": stage.enabled,
                "status": "planned" if stage.enabled else "skipped",
                "duration_seconds": 0.0,
                "error": "",
            }
        )
    return records


# ── Pipeline orchestration ──────────────────────────────────────────────────

def run_pipeline(
    config: dict,
    only: list[str] | None = None,
    skip: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the full pipeline. Returns a summary dict."""
    config = _ensure_config(config)
    stages = _apply_stage_filters(_build_stages(config), only=only, skip=skip)

    log_dir = _resolve_log_dir(config)
    t0 = time.monotonic()
    records: list[dict] = []

    if dry_run:
        records = _build_dry_run_records(stages)
    else:
        _write_pid(log_dir)
        try:
            for stage in stages:
                records.append(_run_stage(stage, config))
        finally:
            _remove_pid(log_dir)

    summary = {
        "started_at": time.time() - (time.monotonic() - t0),
        "finished_at": time.time(),
        "duration_seconds": round(time.monotonic() - t0, 3),
        "dry_run": dry_run,
        "stages": records,
    }

    summary_path = log_dir / _SUMMARY_FILENAME
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


# ── CLI ─────────────────────────────────────────────────────────────────────

def _cmd_status(log_dir: Path) -> None:
    pid_file = log_dir / _PID_FILENAME
    summary_file = log_dir / _SUMMARY_FILENAME
    scheduler_state_file = log_dir / "scheduler_state.json"

    print()
    if pid_file.exists():
        print(f"Pipeline runner PID: {pid_file.read_text(encoding='utf-8').strip()}")
    else:
        print("No active pipeline runner process detected.")

    if scheduler_state_file.exists():
        try:
            sched = json.loads(scheduler_state_file.read_text(encoding="utf-8"))
            print(f"\nScheduler state:")
            print(f"  Total ticks:  {sched.get('total_ticks', 0)}")
            print(f"  Last tick:    {sched.get('last_tick_iso', 'never')}")
            print(f"  Last success: {sched.get('last_success_iso', 'never')}")
            stages = sched.get("stages", {})
            failing = {k: v for k, v in stages.items() if v.get("consecutive_failures", 0) > 0}
            if failing:
                print(f"  Failing stages ({len(failing)}):")
                for name, info in failing.items():
                    print(f"    {name}: {info['consecutive_failures']} consecutive failures — {info.get('last_error', '')[:60]}")
        except Exception:
            pass

    if summary_file.exists():
        data = json.loads(summary_file.read_text(encoding="utf-8"))
        print(f"Last run duration: {data['duration_seconds']}s")
        ok = sum(1 for s in data["stages"] if s["status"] == "ok")
        failed = sum(1 for s in data["stages"] if s["status"] == "failed")
        skipped = sum(1 for s in data["stages"] if s["status"] == "skipped")
        print(f"  OK: {ok}  Failed: {failed}  Skipped: {skipped}")
        print()
        for st in data.get("stages", []):
            mark = {"ok": "+", "failed": "X", "skipped": "-"}.get(st["status"], "?")
            line = f"  [{mark}] {st['stage']}: {st['status']} ({st['duration_seconds']}s)"
            if st.get("error"):
                line += f"  ERROR: {st['error'][:80]}"
            print(line)
    else:
        print("No pipeline summary found yet.")
    print()


def _cmd_list(cfg: dict) -> None:
    """Print all registered stages."""
    stages = _build_stages(cfg)
    print(f"\n{'Stage':<32} {'Enabled':<8} {'Group':<16} {'Module':<40}")
    print("-" * 108)
    for st in stages:
        enabled = "yes" if st.enabled else "no"
        print(f"  {st.name:<30} {enabled:<8} {(st.group or ''):<16} {st.module:<40}")
    print()


def _cmd_dashboard(cfg: dict, output: Path) -> None:
    """Generate static HTML dashboard with document counts per source and last run summary."""
    try:
        from hytools.ingestion._shared.helpers import open_mongodb_client
    except ImportError:
        print("MongoDB helpers not available; dashboard requires ingestion._shared.helpers")
        return
    with open_mongodb_client(cfg) as client:
        if client is None:
            print("MongoDB unavailable; cannot build dashboard")
            return
        counts: list[tuple[str, int]] = []
        branch_counts: list[tuple[str, int]] = []
        try:
            pipeline = [{"$group": {"_id": "$source", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
            for doc in client.documents.aggregate(pipeline):
                counts.append((doc["_id"], doc["count"]))

            branch_pipeline = [{"$group": {"_id": "$metadata.internal_language_branch", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
            for doc in client.documents.aggregate(branch_pipeline):
                branch = doc.get("_id") or "unknown"
                branch_counts.append((branch, doc["count"]))
        except Exception as e:
            logger.warning("Dashboard aggregate failed: %s", e)
        total_docs = sum(c for _, c in counts)
        meta = client.get_latest_metadata("frequency_aggregator") or {}
        drift_meta = client.get_latest_metadata("drift_detection") or {}
        summary_ts = str(meta.get("timestamp", ""))
        entries_stored = meta.get("entries_stored", 0)
        drift_max = drift_meta.get("max_drift", 0.0)
        drift_mean = drift_meta.get("mean_drift", 0.0)
        drift_warn = drift_max > float(cfg.get("drift_threshold", 0.05))
        coverage_summary = None
        if hasattr(client, "coverage_gaps"):
            coverage_summary = client.coverage_gaps.find_one({}, {"_id": 0, "inventory_coverage": 1, "summary": 1}) or None
        acquisition_summary = None
        acquisition_rows: list[dict[str, Any]] = []
        coverage_rows: list[dict[str, Any]] = []
        if hasattr(client, "acquisition_priorities"):
            acquisition_summary = client.acquisition_priorities.find_one(
                {},
                {"_id": 0, "high": 1, "all": 1, "high_count": 1, "all_count": 1, "high_preview": 1},
            ) or None
        try:
            acquisition_items = getattr(client, "acquisition_priority_items", None)
            if acquisition_items is not None:
                acquisition_rows = list(
                    acquisition_items.find(
                        {"priority_filter": {"$in": ["high", "medium"]}},
                        {"_id": 0, "priority_filter": 1, "priority": 1, "type": 1, "description": 1, "action": 1, "acquisition_query": 1, "source_targets": 1, "impact_score": 1},
                    )
                    .sort([("priority_filter", 1), ("impact_score", -1), ("row_index", 1)])
                    .limit(250)
                )
            coverage_items = getattr(client, "coverage_gap_items", None)
            if coverage_items is not None:
                coverage_rows = list(
                    coverage_items.find(
                        {"priority": {"$in": ["high", "medium"]}},
                        {"_id": 0, "priority": 1, "type": 1, "description": 1, "recommended_action": 1, "acquisition_query": 1, "impact_score": 1},
                    )
                    .sort([("priority", 1), ("impact_score", -1), ("row_index", 1)])
                    .limit(250)
                )
        except Exception as e:
            logger.warning("Dashboard detail rows failed: %s", e)
        review_summary = None
        review_rows: list[dict[str, Any]] = []
        try:
            review_coll = getattr(client, "review_queue", None)
            if review_coll is not None:
                open_query = {"reviewed": {"$ne": True}}
                review_summary = {
                    "open_total": review_coll.count_documents(open_query),
                    "high_priority": review_coll.count_documents({**open_query, "priority": 1}),
                    "sources": list(
                        review_coll.aggregate(
                            [
                                {"$match": open_query},
                                {"$group": {"_id": "$stage", "count": {"$sum": 1}}},
                                {"$sort": {"count": -1, "_id": 1}},
                            ]
                        )
                    ),
                }
                review_rows = list(
                    review_coll.find(open_query, {"_id": 0, "run_id": 1, "stage": 1, "reason": 1, "priority": 1, "title": 1, "created_at": 1})
                    .sort([("priority", 1), ("created_at", -1)])
                    .limit(8)
                )
        except Exception as e:
            logger.warning("Dashboard review summary failed: %s", e)

    output.parent.mkdir(parents=True, exist_ok=True)
    total_docs = total_docs or 1
    rows = "".join(
        f"<tr><td>{src}</td><td>{cnt}</td><td>{100*cnt/total_docs:.1f}%</td></tr>"
        for src, cnt in counts
    )
    branch_rows = "".join(
        f"<tr><td>{branch}</td><td>{cnt}</td><td>{100*cnt/total_docs:.1f}%</td></tr>"
        for branch, cnt in branch_counts
    )
    inventory_coverage = (coverage_summary or {}).get("inventory_coverage") or {}
    high_priority_count = int((acquisition_summary or {}).get("high_count", len((acquisition_summary or {}).get("high") or [])) or 0)
    total_priority_count = int((acquisition_summary or {}).get("all_count", len((acquisition_summary or {}).get("all") or [])) or 0)
    detail_output = output.with_name(f"{output.stem}{_DASHBOARD_DETAIL_SUFFIX}{output.suffix}")
    detail_link_html = ""
    if acquisition_rows or coverage_rows or review_rows:
        detail_link_html = f'<p><a href="{html.escape(detail_output.name)}">Open detail dashboard</a> for itemized acquisition, coverage, and review browsing.</p>'
    coverage_html = ""
    if inventory_coverage:
        coverage_html = (
            f"<h2>Inventory coverage</h2>"
            f"<p>Total books: <strong>{inventory_coverage.get('total_books', 0)}</strong> — "
            f"In corpus: <strong>{inventory_coverage.get('books_in_corpus', 0)}</strong> — "
            f"Coverage: <strong>{inventory_coverage.get('coverage_percentage', 0.0):.1f}%</strong></p>"
            f"<p>High-priority acquisition items: <strong>{high_priority_count}</strong> / {total_priority_count}</p>"
        )
        preview_rows = "".join(
            f"<tr><td>{html.escape(str(row.get('priority', '')))}</td><td>{html.escape(str(row.get('type', '')))}</td><td>{html.escape(str(row.get('description', '')))}</td><td>{html.escape(str(row.get('acquisition_query', '')))}</td></tr>"
            for row in ((acquisition_summary or {}).get("high_preview") or [])[:8]
        )
        if preview_rows:
            coverage_html += (
                "<h3>High-priority acquisitions</h3>"
                "<table><thead><tr><th>P</th><th>Type</th><th>Description</th><th>Query</th></tr></thead>"
                f"<tbody>{preview_rows}</tbody></table>"
            )
        coverage_html += detail_link_html
    review_html = ""
    if review_summary is not None:
        review_stage_rows = "".join(
            f"<tr><td>{html.escape(str(row.get('_id') or 'unknown'))}</td><td>{row.get('count', 0)}</td></tr>"
            for row in review_summary.get("sources", [])
        )
        review_item_rows = "".join(
            f"<tr><td>{html.escape(str(row.get('priority', '')))}</td><td>{html.escape(str(row.get('stage', '')))}</td><td>{html.escape(str(row.get('reason', '')))}</td><td>{html.escape(str(row.get('title') or row.get('run_id', '')))}</td></tr>"
            for row in review_rows
        )
        review_html = (
            f"<h2>Review Queue</h2>"
            f"<p>Open items: <strong>{review_summary.get('open_total', 0)}</strong> — "
            f"Priority 1 items: <strong>{review_summary.get('high_priority', 0)}</strong></p>"
            f"<table><thead><tr><th>Stage</th><th>Open items</th></tr></thead><tbody>{review_stage_rows}</tbody></table>"
            f"<h3>Recent review items</h3>"
            f"<table><thead><tr><th>P</th><th>Stage</th><th>Reason</th><th>Title / Run ID</th></tr></thead><tbody>{review_item_rows}</tbody></table>"
        )
        if not coverage_html:
            review_html += detail_link_html
    summary_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Scraper Dashboard</title>
<style>body{{font-family:sans-serif;margin:1rem;}} table{{border-collapse:collapse;}} th,td{{border:1px solid #ccc;padding:6px 12px;text-align:left;}} th{{background:#eee;}}</style>
</head><body>
<h1>Armenian corpus scraper dashboard</h1>
<p>Generated: {summary_ts} — Total documents: <strong>{total_docs}</strong> — Word frequency entries: <strong>{entries_stored}</strong></p>
<p>Drift detection: max {drift_max:.4f}, mean {drift_mean:.4f}. <strong style="color: {"red" if drift_warn else "green"};">{'ALERT' if drift_warn else 'normal'}</strong></p>
{coverage_html}
{review_html}
<h2>Documents by source</h2>
<table><thead><tr><th>Source</th><th>Count</th><th>%</th></tr></thead><tbody>
{rows}
</tbody></table>
<h2>Documents by language branch</h2>
<table><thead><tr><th>Language Branch</th><th>Count</th><th>%</th></tr></thead><tbody>
{branch_rows}
</tbody></table>
<p><small>Run: python -m hytools.ingestion.runner dashboard --output {output}</small></p>
</body></html>"""
    output.write_text(summary_html, encoding="utf-8")
    if acquisition_rows or coverage_rows or review_rows:
        def render_source_targets(row: dict[str, Any]) -> str:
            rendered_targets = []
            for target in row.get("source_targets") or []:
                source = str(target.get("source", "")).strip()
                query = str(target.get("query", "")).strip()
                if not source:
                    continue
                query_param = quote_plus(query)
                if source == "worldcat":
                    href = f"https://search.worldcat.org/search?q={query_param}"
                elif source == "archive_org":
                    href = f"https://archive.org/search?query={query_param}"
                elif source == "hathitrust":
                    href = f"https://catalog.hathitrust.org/Search/Home?lookfor={query_param}"
                elif source == "gallica":
                    href = f"https://gallica.bnf.fr/services/engine/search/sru?operation=searchRetrieve&version=1.2&query={query_param}"
                elif source == "nayiri":
                    href = f"https://nayiri.com/search?query={query_param}"
                else:
                    href = ""
                label = html.escape(source)
                if href:
                    rendered_targets.append(f'<a href="{html.escape(href)}" target="_blank" rel="noreferrer">{label}</a>')
                else:
                    rendered_targets.append(label)
            return "<br/>".join(rendered_targets) or "-"

        acquisition_detail_rows = "".join(
            "<tr data-row>"
            f"<td>{html.escape(str(row.get('priority_filter', '')))}</td>"
            f"<td>{html.escape(str(row.get('type', '')))}</td>"
            f"<td>{html.escape(str(row.get('description', '')))}</td>"
            f"<td>{html.escape(str(row.get('action', '')))}</td>"
            f"<td>{html.escape(str(row.get('acquisition_query', '')))}</td>"
            f"<td>{render_source_targets(row)}</td>"
            "</tr>"
            for row in acquisition_rows
        )
        coverage_detail_rows = "".join(
            "<tr data-row>"
            f"<td>{html.escape(str(row.get('priority', '')))}</td>"
            f"<td>{html.escape(str(row.get('type', '')))}</td>"
            f"<td>{html.escape(str(row.get('description', '')))}</td>"
            f"<td>{html.escape(str(row.get('recommended_action', '')))}</td>"
            f"<td>{html.escape(str(row.get('acquisition_query', '')))}</td>"
            "</tr>"
            for row in coverage_rows
        )
        review_detail_rows = "".join(
            "<tr data-row>"
            f"<td>{html.escape(str(row.get('priority', '')))}</td>"
            f"<td>{html.escape(str(row.get('stage', '')))}</td>"
            f"<td>{html.escape(str(row.get('reason', '')))}</td>"
            f"<td>{html.escape(str(row.get('title') or row.get('run_id', '')))}</td>"
            f"<td>{html.escape(str(row.get('created_at', '')))}</td>"
            "</tr>"
            for row in review_rows
        )
        detail_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Scraper Dashboard Details</title>
<style>
body{{font-family:sans-serif;margin:1rem;}}
table{{border-collapse:collapse;width:100%;margin-bottom:1.5rem;}}
th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left;vertical-align:top;}}
th{{background:#eee;}}
input{{padding:0.5rem;min-width:22rem;margin-bottom:1rem;}}
.muted{{color:#555;}}
</style>
<script>
function filterRows() {{
  const term = document.getElementById('table-filter').value.toLowerCase();
  document.querySelectorAll('[data-row]').forEach((row) => {{
    row.style.display = row.textContent.toLowerCase().includes(term) ? '' : 'none';
  }});
}}
</script>
</head><body>
<h1>Dashboard detail view</h1>
<p><a href="{html.escape(output.name)}">Back to summary dashboard</a></p>
<p class="muted">This page exposes itemized rows to drive catalog and review backfill. The tables are intentionally capped to recent actionable rows for static browsing.</p>
<label for="table-filter">Filter rows</label><br/>
<input id="table-filter" type="search" oninput="filterRows()" placeholder="Search titles, authors, stages, reasons" />
<h2>Acquisition backfill queue</h2>
<table><thead><tr><th>Band</th><th>Type</th><th>Description</th><th>Action</th><th>Query</th><th>Suggested sources</th></tr></thead><tbody>{acquisition_detail_rows}</tbody></table>
<h2>Coverage gaps</h2>
<table><thead><tr><th>P</th><th>Type</th><th>Description</th><th>Recommended action</th><th>Query</th></tr></thead><tbody>{coverage_detail_rows}</tbody></table>
<h2>Open review items</h2>
<table><thead><tr><th>P</th><th>Stage</th><th>Reason</th><th>Title / Run ID</th><th>Created</th></tr></thead><tbody>{review_detail_rows}</tbody></table>
</body></html>"""
        detail_output.write_text(detail_html, encoding="utf-8")
    print(f"Dashboard written to {output}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hytools.ingestion.runner",
        description="Run the full data pipeline: scraping → extraction → post-processing",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run pipeline")
    run_p.add_argument("--background", action="store_true", help="Launch detached background process")
    run_p.add_argument("--only", nargs="*", default=[], help="Only run these stages")
    run_p.add_argument("--skip", nargs="*", default=[], help="Skip these stages")
    run_p.add_argument("--group", choices=["all", "scraping", "extraction", "postprocessing"],
                       default="all", help="Run a predefined group of stages (default: all)")
    run_p.add_argument("--config", type=Path, default=None, help="Path to YAML config file")
    run_p.add_argument("--dry-run", action="store_true", help="Resolve enabled stages and write a planned summary without executing any stage")

    sub.add_parser("status", help="Show pipeline status and last summary")
    list_p = sub.add_parser("list", help="List all registered stages")
    list_p.add_argument("--config", type=Path, default=None, help="Path to YAML config file")
    dash_p = sub.add_parser("dashboard", help="Generate scraper dashboard HTML")
    dash_p.add_argument("--output", type=Path, default=Path("data/logs/scraper_dashboard.html"))
    dash_p.add_argument("--config", type=Path, default=None)

    doctor_p = sub.add_parser("doctor", help="Validate config, stage defaults, paths, credentials, and optional dependencies")
    doctor_p.add_argument("--config", type=Path, default=None, help="Path to YAML config file")
    doctor_p.add_argument("--json", action="store_true", help="Emit the doctor report as JSON")

    sched_p = sub.add_parser("schedule", help="Run pipeline on a repeating schedule (Phase 2)")
    sched_p.add_argument("--interval", type=int, default=None,
                         help="Seconds between pipeline ticks (default: 21600 = 6h)")
    sched_p.add_argument("--alert-window", type=int, default=None,
                         help="Alert if no success within this many seconds (default: 86400 = 24h)")
    sched_p.add_argument("--alert-file", type=Path, default=None,
                         help="Append alerts as JSONL to this file")
    sched_p.add_argument("--only", nargs="*", default=[], help="Only run these stages")
    sched_p.add_argument("--skip", nargs="*", default=[], help="Skip these stages")
    sched_p.add_argument("--config", type=Path, default=None, help="Path to YAML config file")
    sched_p.add_argument("--max-ticks", type=int, default=None,
                         help="Stop after N ticks (default: run forever)")

    release_p = sub.add_parser("release", help="Build a deterministic dataset release from corpus_export")
    release_p.add_argument("--config", type=Path, default=None, help="Path to YAML config file")
    release_p.add_argument("--output", type=Path, default=None, help="Override release output directory")
    release_p.add_argument("--dialect", default=None, help="Override export dialect filter")
    release_p.add_argument("--seed", default=None, help="Override deterministic split seed")
    release_p.add_argument("--dataset-name", default=None, help="Override release dataset name")
    release_p.add_argument("--dataset-version", default=None, help="Override release dataset version")
    release_p.add_argument("--no-huggingface", action="store_true", help="Skip Hugging Face release artifacts")

    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = _build_parser()

    args = parser.parse_args()

    try:
        cfg, resolved_config_path = _load_runner_config(getattr(args, "config", None))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        if SettingsValidationError is not None and isinstance(exc, SettingsValidationError):
            print(f"Invalid config: {exc}", file=sys.stderr)
            return 2
        raise

    if args.command == "doctor":
        from hytools.ingestion.doctor import format_doctor_report, run_doctor

        report = run_doctor(
            cfg,
            config_path=resolved_config_path,
            transition_notices=_collect_stage_transition_notices(cfg),
        )
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_doctor_report(report))
        return 1 if report.errors else 0

    if args.command == "dashboard":
        _cmd_dashboard(cfg, getattr(args, "output", Path("data/logs/scraper_dashboard.html")))
        return 0

    if args.command == "schedule":
        from hytools.ingestion.scheduler import run_scheduler, DEFAULT_INTERVAL_SECONDS, DEFAULT_ALERT_WINDOW_SECONDS
        _emit_stage_transition_notices(cfg)
        run_scheduler(
            cfg,
            interval_seconds=args.interval or DEFAULT_INTERVAL_SECONDS,
            alert_window_seconds=getattr(args, "alert_window", None) or DEFAULT_ALERT_WINDOW_SECONDS,
            alert_file=getattr(args, "alert_file", None),
            only=args.only or None,
            skip=args.skip or None,
            max_ticks=getattr(args, "max_ticks", None),
        )
        return 0

    if args.command == "release":
        from hytools.ingestion.aggregation.corpus_export import build_release

        _emit_stage_transition_notices(cfg)
        try:
            result = build_release(
                cfg,
                output_path=args.output,
                dialect_filter=args.dialect,
                split_seed=args.seed,
                dataset_name=args.dataset_name,
                dataset_version=args.dataset_version,
                include_huggingface=False if args.no_huggingface else None,
            )
        except ImportError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "status":
        _cmd_status(_resolve_log_dir(cfg))
        return 0

    if args.command == "list":
        _cmd_list(cfg)
        return 0

    log_dir = _resolve_log_dir(cfg)

    if args.background:
        cmd = [sys.executable, "-m", "hytools.ingestion.runner", "run"]
        if args.only:
            cmd.extend(["--only", *args.only])
        if args.group:
            cmd.extend(["--group", args.group])
        if args.skip:
            cmd.extend(["--skip", *args.skip])
        if args.config:
            cmd.extend(["--config", str(args.config)])

        log_file = log_dir / "pipeline_runner.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        kwargs: dict = {}
        if sys.platform == "win32":
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW

        with open(log_file, "a", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, **kwargs)

        print(f"Launched pipeline runner in background (PID {proc.pid})")
        print(f"Log: {log_file}")
        print("Status: python -m hytools.ingestion.runner status")
        return 0

    only = list(args.only)
    if not only and args.group != "all":
        only = _stage_groups(cfg).get(args.group, [])

    _emit_stage_transition_notices(cfg)
    summary = run_pipeline(cfg, only=only or None, skip=args.skip, dry_run=args.dry_run)
    ok = sum(1 for s in summary["stages"] if s["status"] == "ok")
    failed_stages = [s for s in summary["stages"] if s["status"] == "failed"]
    if summary.get("dry_run"):
        planned = sum(1 for s in summary["stages"] if s["status"] == "planned")
        skipped = sum(1 for s in summary["stages"] if s["status"] == "skipped")
        print(f"\nDry-run completed in {summary['duration_seconds']}s — {planned} planned, {skipped} skipped")
        return 0
    print(f"\nCompleted in {summary['duration_seconds']}s — {ok} OK, {len(failed_stages)} failed")
    for s in failed_stages:
        print(f"  FAILED: {s['stage']} — {s['error'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
