"""Unified scraping runner.

Runs all scraping sources in sequence with per-source error isolation,
optional background mode, and a machine-readable summary file.

Examples
--------

Run all configured sources::

    python -m armenian_corpus_core.scraping.runner run

Run in background::

    python -m armenian_corpus_core.scraping.runner run --background

Run only selected stages::

    python -m armenian_corpus_core.scraping.runner run --only wikipedia archive_org

Check last summary::

    python -m armenian_corpus_core.scraping.runner status
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
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LOG_DIR = Path("data") / "logs"
_PID_FILENAME = ".scrape_runner.pid"
_SUMMARY_FILENAME = "scrape_summary.json"


@dataclass
class Stage:
    name: str
    module: str
    enabled: bool = True


def _build_stages(cfg: dict) -> list[Stage]:
    scraping_cfg = cfg.get("scraping", {})

    def _enabled(key: str) -> bool:
        return scraping_cfg.get(key, {}).get("enabled", True)

    stages = [
        Stage("wikipedia", "armenian_corpus_core.scraping.wikipedia", enabled=_enabled("wikipedia")),
        Stage("wikisource", "armenian_corpus_core.scraping.wikisource", enabled=_enabled("wikisource")),
        Stage("archive_org", "armenian_corpus_core.scraping.archive_org", enabled=_enabled("archive_org")),
        Stage("culturax", "armenian_corpus_core.scraping.culturax", enabled=_enabled("culturax")),
        Stage("hathitrust", "armenian_corpus_core.scraping.hathitrust", enabled=_enabled("hathitrust")),
        Stage("loc", "armenian_corpus_core.scraping.loc", enabled=_enabled("loc")),
        Stage("newspaper", "armenian_corpus_core.scraping.newspaper", enabled=_enabled("newspapers")),
        Stage("nayiri", "armenian_corpus_core.scraping.nayiri", enabled=_enabled("nayiri")),
        Stage("eastern_armenian", "armenian_corpus_core.scraping.eastern_armenian", enabled=_enabled("eastern_armenian")),
        Stage("rss_news", "armenian_corpus_core.scraping.rss_news", enabled=_enabled("rss_news")),
        Stage("english_sources", "armenian_corpus_core.scraping.english_sources", enabled=_enabled("english_sources")),
        Stage("frequency_aggregator", "armenian_corpus_core.scraping.frequency_aggregator", enabled=_enabled("frequency_aggregator")),
    ]
    return stages


def _resolve_log_dir(cfg: dict) -> Path:
    """Determine the log directory from config or use default."""
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
    rec = {
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
        if not hasattr(mod, "run"):
            raise RuntimeError(f"Module has no run() entrypoint: {stage.module}")

        logger.info("Running stage: %s", stage.name)

        # Check if MongoDB is enabled and module supports it
        use_mongodb = cfg.get("database", {}).get("use_mongodb", False)
        mongodb_supported_modules = [
            "armenian_corpus_core.scraping.wikipedia",
            "armenian_corpus_core.scraping.wikisource",
        ]

        if use_mongodb and stage.module in mongodb_supported_modules:
            sig = inspect.signature(mod.run)
            if "use_mongodb" in sig.parameters:
                logger.info("  MongoDB mode enabled for %s", stage.name)
                mod.run(cfg, use_mongodb=True)
            else:
                logger.warning("  MongoDB enabled but %s doesn't support it yet", stage.name)
                mod.run(cfg)
        else:
            mod.run(cfg)

        rec["status"] = "ok"
    except Exception as exc:
        logger.exception("Stage failed: %s", stage.name)
        rec["status"] = "failed"
        rec["error"] = str(exc)
    finally:
        rec["duration_seconds"] = round(time.monotonic() - t0, 3)
    return rec


def run_pipeline(
    config: dict,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> dict:
    """Run the scraping pipeline with the given configuration.

    Args:
        config: Full configuration dict (paths, scraping settings, etc.)
        only: If set, only run stages with these names.
        skip: If set, skip stages with these names.

    Returns:
        Summary dict with timing and per-stage results.
    """
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


def _cmd_status(log_dir: Path) -> None:
    pid_file = log_dir / _PID_FILENAME
    summary_file = log_dir / _SUMMARY_FILENAME

    print()
    if pid_file.exists():
        print(f"Scraping runner PID: {pid_file.read_text(encoding='utf-8').strip()}")
    else:
        print("No active scraping runner process detected.")

    if summary_file.exists():
        data = json.loads(summary_file.read_text(encoding="utf-8"))
        print(f"Last run duration: {data['duration_seconds']}s")
        for st in data.get("stages", []):
            print(f"- {st['stage']}: {st['status']} ({st['duration_seconds']}s)")
    else:
        print("No scrape summary found yet.")
    print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="python -m armenian_corpus_core.scraping.runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run scraping pipeline")
    run_p.add_argument("--background", action="store_true", help="Launch detached background process")
    run_p.add_argument("--only", nargs="*", default=[], help="Only run these stages")
    run_p.add_argument("--skip", nargs="*", default=[], help="Skip these stages")
    run_p.add_argument("--config", type=Path, default=None, help="Path to YAML config file")

    sub.add_parser("status", help="Show pipeline status and last summary")

    args = parser.parse_args()

    # Load config
    cfg: dict = {}
    if args.command == "run" and args.config:
        import yaml
        with open(args.config, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

    log_dir = _resolve_log_dir(cfg)

    if args.command == "status":
        _cmd_status(log_dir)
        return

    if args.background:
        cmd = [sys.executable, "-m", "armenian_corpus_core.scraping.runner", "run"]
        if args.only:
            cmd.extend(["--only", *args.only])
        if args.skip:
            cmd.extend(["--skip", *args.skip])
        if args.config:
            cmd.extend(["--config", str(args.config)])

        log_file = log_dir / "scraping_runner.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        kwargs: dict = {}
        if sys.platform == "win32":
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW

        with open(log_file, "a", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, **kwargs)

        print(f"Launched scraping runner in background (PID {proc.pid})")
        print(f"Log: {log_file}")
        print("Status: python -m armenian_corpus_core.scraping.runner status")
        return

    summary = run_pipeline(cfg, only=args.only, skip=args.skip)
    failed = [s for s in summary["stages"] if s["status"] == "failed"]
    print(f"Completed in {summary['duration_seconds']}s")
    print(f"Failed stages: {len(failed)}")


if __name__ == "__main__":
    main()
