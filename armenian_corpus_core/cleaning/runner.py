"""Unified cleaning runner for scraped text.

Pipeline:
1. Collect text from `data/raw/**` into a staging text directory.
2. Normalize text into `data/cleaned`.
3. Deduplicate into `data/deduped`.
4. Filter Western Armenian into `data/filtered`.
5. Promote filtered corpus back into `data/cleaned` for training/augmentation.

Examples
--------

Run cleaning:
    python -m src.cleaning.runner run

Run in background:
    python -m src.cleaning.runner run --background

Status:
    python -m src.cleaning.runner status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parents[2]
_SETTINGS_PATH = _ROOT / "config" / "settings.yaml"
_PID_FILE = _ROOT / "data" / "logs" / ".clean_runner.pid"
_SUMMARY_FILE = _ROOT / "data" / "logs" / "clean_summary.json"


def _load_config() -> dict:
    with open(_SETTINGS_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _write_pid() -> None:
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _safe_clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_tree(src: Path, dst: Path) -> int:
    count = 0
    for f in src.rglob("*.txt"):
        rel = f.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        count += 1
    return count


def _extract_culturax_jsonl(raw_dir: Path, stage_dir: Path) -> int:
    """Convert CulturaX JSONL docs into .txt files for downstream cleaning."""
    import hashlib

    count = 0
    for jsonl in (raw_dir / "culturax").rglob("*.jsonl"):
        with open(jsonl, encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = obj.get("text") or obj.get("content") or obj.get("raw_content") or ""
                if not isinstance(text, str) or not text.strip():
                    continue
                h = hashlib.sha1(text[:200].encode("utf-8", errors="ignore")).hexdigest()[:16]
                out = stage_dir / "culturax" / f"{h}.txt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
                count += 1
    return count


def _collect_raw_text(raw_dir: Path, stage_dir: Path) -> dict:
    """Aggregate all scrape outputs into one staging text directory."""
    _safe_clear_dir(stage_dir)
    stats = {"txt_copied": 0, "culturax_docs": 0}

    stats["txt_copied"] = _copy_tree(raw_dir, stage_dir)
    stats["culturax_docs"] = _extract_culturax_jsonl(raw_dir, stage_dir)

    return stats


def run_pipeline(promote_filtered: bool = True) -> dict:
    # Lazy imports so CLI help/status can work even if optional deps are missing.
    from .dedup import deduplicate_files
    from .language_filter import filter_directory
    from .normalizer import normalize_directory

    cfg = _load_config()

    data_root = _ROOT / cfg["paths"]["data_root"]
    raw_dir = _ROOT / cfg["paths"]["raw_dir"]
    cleaned_dir = _ROOT / cfg["paths"]["cleaned_dir"]
    staging_dir = data_root / "staging_text"
    dedup_dir = data_root / "deduped"
    filtered_dir = data_root / "filtered"

    clean_cfg = cfg.get("cleaning", {})
    min_chars = int(clean_cfg.get("min_chars_per_doc", 100))
    threshold = float(clean_cfg.get("minhash_threshold", 0.85))
    num_perm = int(clean_cfg.get("minhash_num_perm", 128))

    _write_pid()
    t0 = time.monotonic()
    summary: dict = {
        "started_at": time.time(),
        "steps": {},
        "errors": [],
    }

    try:
        # 1) Collect raw text
        t = time.monotonic()
        collect_stats = _collect_raw_text(raw_dir, staging_dir)
        summary["steps"]["collect_raw"] = {
            "status": "ok",
            "duration_seconds": round(time.monotonic() - t, 3),
            **collect_stats,
        }

        # 2) Normalize
        t = time.monotonic()
        _safe_clear_dir(cleaned_dir)
        normalize_directory(staging_dir, cleaned_dir)
        normalized_count = sum(1 for _ in cleaned_dir.rglob("*.txt"))
        summary["steps"]["normalize"] = {
            "status": "ok",
            "duration_seconds": round(time.monotonic() - t, 3),
            "files": normalized_count,
        }

        # 3) Deduplicate
        t = time.monotonic()
        _safe_clear_dir(dedup_dir)
        total, kept = deduplicate_files(cleaned_dir, dedup_dir, threshold=threshold, num_perm=num_perm)
        summary["steps"]["dedup"] = {
            "status": "ok",
            "duration_seconds": round(time.monotonic() - t, 3),
            "total": total,
            "kept": kept,
        }

        # 4) Western Armenian filter
        t = time.monotonic()
        _safe_clear_dir(filtered_dir)
        f_total, f_kept = filter_directory(dedup_dir, filtered_dir, require_western=True, min_chars=min_chars)
        summary["steps"]["wa_filter"] = {
            "status": "ok",
            "duration_seconds": round(time.monotonic() - t, 3),
            "total": f_total,
            "kept": f_kept,
        }

        # 5) Promote filtered corpus back to cleaned_dir for downstream jobs.
        if promote_filtered:
            t = time.monotonic()
            _safe_clear_dir(cleaned_dir)
            promoted = _copy_tree(filtered_dir, cleaned_dir)
            summary["steps"]["promote_filtered"] = {
                "status": "ok",
                "duration_seconds": round(time.monotonic() - t, 3),
                "files": promoted,
            }

    except Exception as exc:  # pragma: no cover - operational path
        logger.exception("Cleaning pipeline failed")
        summary["errors"].append(str(exc))
    finally:
        summary["finished_at"] = time.time()
        summary["duration_seconds"] = round(time.monotonic() - t0, 3)
        _SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        _remove_pid()

    return summary


def _launch_background() -> None:
    cmd = [sys.executable, "-m", "armenian_corpus_core.cleaning.runner", "run"]
    log_file = _ROOT / "data" / "logs" / "cleaning_runner.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict = {}
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW

    with open(log_file, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=lf, stderr=subprocess.STDOUT, **kwargs)

    print(f"Launched cleaning runner in background (PID {proc.pid})")
    print(f"Log: {log_file}")
    print("Status: python -m src.cleaning.runner status")


def _cmd_status() -> None:
    print()
    if _PID_FILE.exists():
        print(f"Cleaning runner PID: {_PID_FILE.read_text(encoding='utf-8').strip()}")
    else:
        print("No active cleaning runner process detected.")

    if _SUMMARY_FILE.exists():
        data = json.loads(_SUMMARY_FILE.read_text(encoding="utf-8"))
        print(f"Last run duration: {data.get('duration_seconds', 0)}s")
        for step, info in data.get("steps", {}).items():
            print(f"- {step}: {info.get('status')} ({info.get('duration_seconds', 0)}s)")
    else:
        print("No cleaning summary found yet.")
    print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="python -m src.cleaning.runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run cleaning pipeline")
    run_p.add_argument("--background", action="store_true", help="Launch detached background process")

    sub.add_parser("status", help="Show status and last summary")

    args = parser.parse_args()

    if args.command == "status":
        _cmd_status()
        return

    if args.background:
        _launch_background()
        return

    summary = run_pipeline(promote_filtered=True)
    print(f"Completed in {summary.get('duration_seconds', 0)}s")
    print(f"Errors: {len(summary.get('errors', []))}")


if __name__ == "__main__":
    main()
