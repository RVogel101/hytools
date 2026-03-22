"""Unified ingestion pipeline runner — acquisition + extraction + enrichment + aggregation.

Runs every data-acquisition and processing stage in sequence with per-stage
error isolation, optional background mode, and a machine-readable summary.

Usage
-----
Run everything::

    python -m ingestion.runner run

Run in background::

    python -m ingestion.runner run --background

Run only selected stages::

    python -m ingestion.runner run --only wikipedia archive_org

Skip stages::

    python -m ingestion.runner run --skip news gallica

Check last summary::

    python -m ingestion.runner status
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LOG_DIR = Path("data") / "logs"
_PID_FILENAME = ".pipeline_runner.pid"
_SUMMARY_FILENAME = "pipeline_summary.json"


@dataclass
class Stage:
    name: str
    module: str
    enabled: bool = True
    has_run: bool = True
    has_main: bool = False
    supports_mongodb: bool = False
    entry_point: str | None = None  # if set, call this instead of run() (e.g. ingestion.acquisition.wiki: run_wikipedia / run_wikisource)


def _build_stages(cfg: dict) -> list[Stage]:
    """Build the complete ordered list of pipeline stages.

    Stages live under ingestion (acquisition, discovery, extraction, enrichment,
    aggregation, validation). Config is read from hytools.ingestion.* or scraping.* for backward compatibility.
    """
    ing_cfg = {**cfg.get("scraping", {}), **cfg.get("ingestion", {})}

    def _on(key: str) -> bool:
        return ing_cfg.get(key, {}).get("enabled", True) if isinstance(ing_cfg.get(key), dict) else True

    return [
        # ── Acquisition: Wikimedia ────────────────────────────────────────
        Stage("wikipedia",       "ingestion.acquisition.wiki",            enabled=_on("wikipedia"),         supports_mongodb=True, entry_point="run_wikipedia"),
        Stage("wikisource",      "ingestion.acquisition.wiki",            enabled=_on("wikisource"),        supports_mongodb=True, entry_point="run_wikisource"),

        # ── Acquisition: Digital libraries ───────────────────────────────
        Stage("archive_org",     "ingestion.acquisition.archive_org",     enabled=_on("archive_org"),       supports_mongodb=True),
        Stage("hathitrust",      "ingestion.acquisition.hathitrust",      enabled=_on("hathitrust"),        supports_mongodb=True),
        Stage("gallica",         "ingestion.acquisition.gallica",         enabled=_on("gallica"),           supports_mongodb=True),
        Stage("loc",             "ingestion.acquisition.loc",             enabled=_on("loc"),               supports_mongodb=True),
        Stage("dpla",            "ingestion.acquisition.dpla",            enabled=_on("dpla"),              supports_mongodb=True),

        # ── Acquisition: News (diaspora newspapers + EA agencies + RSS) ───
        Stage("news",            "ingestion.acquisition.news",            enabled=_on("newspapers") or _on("eastern_armenian") or _on("rss_news"), supports_mongodb=True),

        # ── Acquisition: Datasets ────────────────────────────────────────
        Stage("culturax",        "ingestion.acquisition.culturax",        enabled=_on("culturax"),          supports_mongodb=True),
        Stage("opus",            "ingestion.acquisition.opus",            enabled=_on("opus"),              supports_mongodb=True),
        Stage("jw",              "ingestion.acquisition.jw",              enabled=_on("jw"),                supports_mongodb=True),
        Stage("english_sources", "ingestion.acquisition.english_sources",  enabled=_on("english_sources"),  supports_mongodb=True),

        # ── Acquisition: Reference ───────────────────────────────────────
        Stage("nayiri",          "ingestion.acquisition.nayiri",          enabled=_on("nayiri"),            supports_mongodb=True),
        Stage("gomidas",         "ingestion.acquisition.gomidas",         enabled=_on("gomidas"),         supports_mongodb=True),
        Stage("mechitarist",    "ingestion.acquisition.mechitarist",     enabled=_on("mechitarist"),    supports_mongodb=True),
        Stage("agbu",           "ingestion.acquisition.agbu",            enabled=_on("agbu"),           supports_mongodb=True),
        Stage("hamazkayin",     "ingestion.acquisition.hamazkayin",      enabled=_on("hamazkayin"),     supports_mongodb=True),
        Stage("agos",           "ingestion.acquisition.agos",            enabled=_on("agos"),           supports_mongodb=True),
        Stage("ocr_ingest",      "ingestion.acquisition.ocr_ingest",      enabled=_on("ocr_ingest"),      supports_mongodb=True),
        Stage("mss_nkr",         "ingestion.acquisition.mss_nkr",         enabled=_on("mss_nkr"),          supports_mongodb=True),
        Stage("worldcat_searcher", "ingestion.discovery.worldcat_searcher", enabled=_on("worldcat"),      has_run=True, has_main=True),

        # ── Post-processing ──────────────────────────────────────────────
        Stage("cleaning",              "cleaning.run_mongodb",           enabled=_on("cleaning"), has_run=True, has_main=False),
        Stage("metadata_tagger",       "ingestion.enrichment.metadata_tagger",       enabled=_on("metadata_tagger")),
        Stage("frequency_aggregator",      "ingestion.aggregation.frequency_aggregator",      enabled=_on("frequency_aggregator")),
        Stage("incremental_merge",        "ingestion.aggregation.incremental_merge",        enabled=_on("incremental_merge")),
        Stage("word_frequency_facets",   "ingestion.aggregation.word_frequency_facets",   enabled=_on("word_frequency_facets")),
        Stage("drift_detection",          "ingestion.aggregation.drift_detection",          enabled=_on("drift_detection")),
        Stage("export_corpus_overlap_fingerprints", "ingestion.validation.export_corpus_overlap_fingerprints",
              enabled=_on("export_corpus_overlap_fingerprints"), has_run=True, has_main=True),

        # ── Extraction pipeline (all MongoDB-native) ────────────────────
        Stage("import_anki_to_mongodb",                "ingestion.extraction.import_anki_to_mongodb",
              enabled=_on("extraction"), has_run=True, has_main=True),
        Stage("validate_contract_alignment",           "ingestion.validation.validate_contract_alignment",
              enabled=_on("extraction"), has_run=True, has_main=True),
        Stage("materialize_dialect_views",             "ingestion.enrichment.materialize_dialect_views",
              enabled=_on("extraction"), has_run=True, has_main=False),
        Stage("summarize_unified_documents",           "ingestion.aggregation.summarize_unified_documents",
              enabled=_on("extraction"), has_run=True, has_main=False),
    ]


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
        "hathitrust": {},
        "gallica": {},
        "loc": {},
        "dpla": {},
        "ocr_ingest": {},
        "gomidas": {},
        "mechitarist": {},
        "agbu": {},
        "hamazkayin": {},
        "newspapers": {},
        "nayiri": {},
        "eastern_armenian": {},
        "rss_news": {},
        "english_sources": {},
        "worldcat": {},
        "cleaning": {},
        "metadata_tagger": {},
        "frequency_aggregator": {},
        "word_frequency_facets": {},
        "export_corpus_overlap_fingerprints": {},
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


# ── Pipeline orchestration ──────────────────────────────────────────────────

def run_pipeline(
    config: dict,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> dict:
    """Run the full pipeline. Returns a summary dict."""
    config = _ensure_config(config)
    stages = _build_stages(config)

    only_set = set(only or [])
    skip_set = set(skip or [])

    if only_set:
        for st in stages:
            st.enabled = st.enabled and st.name in only_set
    if skip_set:
        for st in stages:
            st.enabled = st.enabled and st.name not in skip_set

    log_dir = _resolve_log_dir(config)
    _write_pid(log_dir)
    t0 = time.monotonic()
    records: list[dict] = []

    try:
        for stage in stages:
            records.append(_run_stage(stage, config))
    finally:
        _remove_pid(log_dir)

    summary = {
        "started_at": time.time() - (time.monotonic() - t0),
        "finished_at": time.time(),
        "duration_seconds": round(time.monotonic() - t0, 3),
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

    print()
    if pid_file.exists():
        print(f"Pipeline runner PID: {pid_file.read_text(encoding='utf-8').strip()}")
    else:
        print("No active pipeline runner process detected.")

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


def _cmd_list() -> None:
    """Print all registered stages."""
    stages = _build_stages({})
    print(f"\n{'Stage':<45} {'Module':<40} {'MongoDB'}")
    print("-" * 95)
    for st in stages:
        mongo = "yes" if st.supports_mongodb else ""
        entry = "run()" if st.has_run else "main()"
        print(f"  {st.name:<43} {st.module:<40} {mongo}")
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
        summary_ts = str(meta.get("timestamp", ""))
        entries_stored = meta.get("entries_stored", 0)

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
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Scraper Dashboard</title>
<style>body{{font-family:sans-serif;margin:1rem;}} table{{border-collapse:collapse;}} th,td{{border:1px solid #ccc;padding:6px 12px;text-align:left;}} th{{background:#eee;}}</style>
</head><body>
<h1>Armenian corpus scraper dashboard</h1>
<p>Generated: {summary_ts} — Total documents: <strong>{total_docs}</strong> — Word frequency entries: <strong>{entries_stored}</strong></p>
<h2>Documents by source</h2>
<table><thead><tr><th>Source</th><th>Count</th><th>%</th></tr></thead><tbody>
{rows}
</tbody></table>
<h2>Documents by language branch</h2>
<table><thead><tr><th>Language Branch</th><th>Count</th><th>%</th></tr></thead><tbody>
{branch_rows}
</tbody></table>
<p><small>Run: python -m ingestion.runner dashboard --output {output}</small></p>
</body></html>"""
    output.write_text(html, encoding="utf-8")
    print(f"Dashboard written to {output}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(
        prog="python -m ingestion.runner",
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

    sub.add_parser("status", help="Show pipeline status and last summary")
    sub.add_parser("list", help="List all registered stages")
    dash_p = sub.add_parser("dashboard", help="Generate scraper dashboard HTML")
    dash_p.add_argument("--output", type=Path, default=Path("data/logs/scraper_dashboard.html"))
    dash_p.add_argument("--config", type=Path, default=None)

    args = parser.parse_args()

    cfg: dict = {}
    if getattr(args, "config", None) and args.config and args.config.exists():
        import yaml
        with open(args.config, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    elif args.command == "run" and args.config:
        import yaml
        with open(args.config, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

    if args.command == "dashboard":
        _cmd_dashboard(cfg, getattr(args, "output", Path("data/logs/scraper_dashboard.html")))
        return

    if args.command == "status":
        _cmd_status(_resolve_log_dir(cfg))
        return

    if args.command == "list":
        _cmd_list()
        return

    log_dir = _resolve_log_dir(cfg)

    if args.background:
        cmd = [sys.executable, "-m", "ingestion.runner", "run"]
        if args.only:
            cmd.extend(["--only", *args.only])
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
        print("Status: python -m ingestion.runner status")
        return

    only = list(args.only)
    if not only and args.group != "all":
        group_map = {
            "scraping": [
                "wikipedia", "wikisource",
                "archive_org", "hathitrust", "gallica", "loc", "dpla",
                "news",
                "culturax", "english_sources",
                "nayiri", "mss_nkr", "worldcat_searcher",
            ],
            "extraction": [
                "import_anki_to_mongodb", "validate_contract_alignment",
                "materialize_dialect_views", "summarize_unified_documents",
            ],
            "postprocessing": [
                "metadata_tagger", "frequency_aggregator",
                "export_corpus_overlap_fingerprints",
            ],
        }
        only = group_map.get(args.group, [])

    summary = run_pipeline(cfg, only=only or None, skip=args.skip)
    ok = sum(1 for s in summary["stages"] if s["status"] == "ok")
    failed_stages = [s for s in summary["stages"] if s["status"] == "failed"]
    print(f"\nCompleted in {summary['duration_seconds']}s — {ok} OK, {len(failed_stages)} failed")
    for s in failed_stages:
        print(f"  FAILED: {s['stage']} — {s['error'][:100]}")


if __name__ == "__main__":
    main()
