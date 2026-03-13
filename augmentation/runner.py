"""CLI entry-point for the WA data augmentation pipeline.

Usage
-----
::

    # Estimate time without running anything
    python -m augmentation.runner estimate

    # Run augmentation (foreground, with progress bar)
    python -m augmentation.runner run

    # Run augmentation as a detached background process
    python -m augmentation.runner run --background

    # Check progress of a running/completed augmentation
    python -m augmentation.runner status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

from augmentation.batch_worker import (
    BatchWorker,
    Checkpoint,
    TimeEstimate,
    WorkerConfig,
    estimate_time,
)
from augmentation.llm_client import LLMConfig

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parents[2]
_SETTINGS = _ROOT / "config" / "settings.yaml"


# ═══════════════════════════════════════════════════════════════════════
# Config loader
# ═══════════════════════════════════════════════════════════════════════

def _load_config() -> tuple[WorkerConfig, LLMConfig]:
    """Read ``config/settings.yaml`` and return augmentation configs."""
    settings: dict = {}
    if _SETTINGS.is_file():
        with open(_SETTINGS, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

    aug = settings.get("augmentation", {})
    llm_cfg = aug.get("llm", {})
    strats = aug.get("strategies", {})
    db_cfg = settings.get("database", {})
    paths_cfg = settings.get("paths", {})

    source_backend = aug.get("source_backend")
    if not source_backend:
        source_backend = "mongodb" if db_cfg.get("use_mongodb", False) else "filesystem"
    output_backend = aug.get("output_backend")
    if not output_backend:
        output_backend = "mongodb" if db_cfg.get("use_mongodb", False) else "filesystem"

    log_dir = _ROOT / paths_cfg.get("log_dir", "data/logs")
    use_mongodb_output = (output_backend or "").strip().lower() == "mongodb"
    if use_mongodb_output:
        log_file = log_dir / "augmentation.log"
    else:
        log_file = _ROOT / aug.get("log_file", "data/augmented/augmentation.log")

    worker = WorkerConfig(
        source_backend=source_backend,
        output_backend=output_backend,
        source_dir=_ROOT / aug.get("source_dir", "data/cleaned"),
        mongodb_uri=db_cfg.get("mongodb_uri", "mongodb://localhost:27017/"),
        mongodb_database=db_cfg.get("mongodb_database", "western_armenian_corpus"),
        mongodb_source_filter=aug.get("mongodb_source_filter", ""),
        mongodb_max_documents=aug.get("mongodb_max_documents", 0),
        allow_filesystem_fallback=aug.get("allow_filesystem_fallback", True),
        output_dir=_ROOT / aug.get("output_dir", "data/augmented"),
        checkpoint_file=_ROOT / aug.get("checkpoint_file", "data/augmented/.checkpoint.jsonl"),
        log_file=log_file,
        log_dir=log_dir if use_mongodb_output else None,
        min_paragraph_chars=aug.get("min_paragraph_chars", 100),
        max_paragraph_chars=aug.get("max_paragraph_chars", 3000),
        min_armenian_ratio=aug.get("min_armenian_ratio", 0.70),
        validate_wa_output=aug.get("validate_wa_output", True),
        max_retries=aug.get("max_retries", 3),
        strict_classical=aug.get("strict_classical", True),
        check_nayiri=aug.get("check_nayiri", False),
        use_safe_wrapper=aug.get("use_safe_wrapper", True),
        sample_ratios={
            "paraphrase":       strats.get("paraphrase", {}).get("sample_ratio", 1.0),
            "continue":         strats.get("continue_text", {}).get("sample_ratio", 0.5),
            "topic_write":      strats.get("topic_write", {}).get("sample_ratio", 0.3),
            "sentence_shuffle": strats.get("sentence_shuffle", {}).get("sample_ratio", 1.0),
            "random_deletion":  strats.get("random_deletion", {}).get("sample_ratio", 0.5),
            "word_dropout":     strats.get("word_dropout", {}).get("sample_ratio", 0.5),
        },
        compute_metrics_per_task=aug.get("compute_metrics_per_task", False),
        enabled_strategies={
            "paraphrase":       strats.get("paraphrase", {}).get("enabled", True),
            "continue":         strats.get("continue_text", {}).get("enabled", True),
            "topic_write":      strats.get("topic_write", {}).get("enabled", True),
            "sentence_shuffle": strats.get("sentence_shuffle", {}).get("enabled", True),
            "random_deletion":  strats.get("random_deletion", {}).get("enabled", True),
            "word_dropout":     strats.get("word_dropout", {}).get("enabled", True),
        },
    )

    llm = LLMConfig(
        base_url=llm_cfg.get("base_url", "http://localhost:11434"),
        model=llm_cfg.get("model", "llama3.1:8b"),
        api_type=llm_cfg.get("api_type", "ollama"),
        temperature=llm_cfg.get("temperature", 0.8),
        max_tokens=llm_cfg.get("max_tokens", 512),
        timeout=llm_cfg.get("timeout", 120),
        max_retries=llm_cfg.get("max_retries", 5),
        base_delay=llm_cfg.get("base_delay", 1.0),
        max_delay=llm_cfg.get("max_delay", 60.0),
        jitter=llm_cfg.get("jitter", 0.25),
    )

    return worker, llm


# ═══════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════

def cmd_estimate(args: argparse.Namespace) -> None:
    """Print a detailed time estimate."""
    worker_cfg, llm_cfg = _load_config()
    print("\nScanning source data and benchmarking LLM …\n")
    est = estimate_time(
        worker_cfg,
        llm_cfg,
        retry_overhead_pct=10.0,
        run_benchmark=not args.skip_benchmark,
    )
    print(est.display())

    if est.total_paragraphs == 0:
        print("  ⚠  No source data found in", worker_cfg.source_dir)
        print("     Run the cleaning pipeline (prepare_training_data) first, then re-run this estimate.")
        print()
        _show_hypothetical_estimate(llm_cfg, worker_cfg, skip_benchmark=args.skip_benchmark)


def cmd_run(args: argparse.Namespace) -> None:
    """Run the augmentation pipeline."""
    if args.background:
        _launch_background()
        return

    worker_cfg, llm_cfg = _load_config()

    # Write PID file so status command can find us.
    _write_pid()

    # Install graceful shutdown handler.
    _install_signal_handler()

    print("\n Starting WA data augmentation pipeline …\n")
    worker = BatchWorker(worker_cfg, llm_cfg)
    stats = worker.run()

    _remove_pid()

    print(f"\n Done.  Success: {stats['success']}, "
          f"Failed: {stats['failed']}, "
          f"Skipped (checkpoint): {stats['skipped_checkpoint']}, "
          f"Skipped (validation): {stats['skipped_validation']}\n")


def _pid_file() -> Path:
    """PID file path: data/logs when MongoDB output, else data/augmented."""
    settings: dict = {}
    if _SETTINGS.is_file():
        with open(_SETTINGS, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
    paths = settings.get("paths", {})
    db = settings.get("database", {})
    aug = settings.get("augmentation", {})
    output_backend = aug.get("output_backend") or ("mongodb" if db.get("use_mongodb") else "filesystem")
    if (output_backend or "").strip().lower() == "mongodb":
        base = _ROOT / paths.get("log_dir", "data/logs")
    else:
        base = _ROOT / aug.get("output_dir", "data/augmented")
    return base / ".augmentation.pid"


def cmd_status(args: argparse.Namespace) -> None:
    """Show progress of a running or completed augmentation."""
    worker_cfg, _ = _load_config()
    ckpt = Checkpoint(worker_cfg.checkpoint_file)

    if worker_cfg.log_dir:
        summary_path = worker_cfg.log_dir / "augmentation_summary.json"
    else:
        summary_path = worker_cfg.output_dir / "summary.json"

    print()
    # Check if running.
    pid_file = _pid_file()
    if pid_file.is_file():
        pid = pid_file.read_text().strip()
        print(f"  Augmentation process PID: {pid}")
        print(f"  (check with: tasklist /FI \"PID eq {pid}\" on Windows)\n")
    else:
        print("  No active augmentation process detected.\n")

    print(f"  Checkpoint tasks completed: {ckpt.completed_count}")

    if summary_path.is_file():
        with open(summary_path, encoding="utf-8") as f:
            stats = json.load(f)
        print(f"  Last run stats: {json.dumps(stats, indent=4)}")

    # Show output directory size.
    if worker_cfg.output_dir.is_dir():
        total_bytes = sum(f.stat().st_size for f in worker_cfg.output_dir.rglob("*.txt"))
        print(f"  Output size: {total_bytes / (1024 * 1024):.2f} MB "
              f"({sum(1 for _ in worker_cfg.output_dir.rglob('*.txt'))} files)")
    print()


def cmd_metrics(args: argparse.Namespace) -> None:
    """Run MetricsComputationPipeline on augmented documents. Store in MongoDB only."""
    settings: dict = {}
    if _SETTINGS.is_file():
        with open(_SETTINGS, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
    db_cfg = settings.get("database", {})
    mongodb_uri = db_cfg.get("mongodb_uri", "mongodb://localhost:27017/")
    mongodb_database = db_cfg.get("mongodb_database", "western_armenian_corpus")

    try:
        from augmentation.metrics_pipeline import MetricsComputationPipeline
    except ImportError:
        from src.augmentation.metrics_pipeline import MetricsComputationPipeline

    try:
        from integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        from src.database.mongodb_client import MongoDBCorpusClient

    print("\n  Post-augmentation metrics (MongoDB only)\n")

    with MongoDBCorpusClient(uri=mongodb_uri, database_name=mongodb_database) as client:
        docs = client.find_documents(source="augmented", limit=args.limit)
        if not docs:
            print("  No augmented documents found in MongoDB. Run augmentation first.")
            return

        pipeline = MetricsComputationPipeline(mongodb_client=client)
        metric_cards = []
        for i, doc in enumerate(docs):
            text = doc.get("text") or ""
            if not text.strip():
                continue
            meta = doc.get("metadata") or {}
            strategy = meta.get("augmentation_strategy", "unknown")
            text_id = meta.get("task_uid", f"aug_{i}")
            card = pipeline.compute_augmented(
                text,
                text_id=text_id,
                source="augmented",
                strategy_name=strategy,
            )
            metric_cards.append(card)

        if not metric_cards:
            print("  No valid augmented texts to compute metrics for.")
            return

        report = pipeline.generate_batch_report(
            batch_id="augmented",
            strategy_name="all",
            metric_cards=metric_cards,
        )
        doc_id = pipeline.save_batch_report_to_mongodb(client, report)

        print(f"  Processed {len(metric_cards)} augmented documents.")
        print(f"  Mean dialect purity: {report.mean_dialect_purity:.4f}")
        print(f"  Mean TTR: {report.mean_vocabulary_diversity:.4f}")
        print(f"  Stored in MongoDB: augmentation_metrics (doc id: {doc_id})")
        print()


def cmd_visualize(args: argparse.Namespace) -> None:
    """Plot metric distributions from augmented documents (MongoDB)."""
    settings: dict = {}
    if _SETTINGS.is_file():
        with open(_SETTINGS, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
    db_cfg = settings.get("database", {})
    mongodb_uri = db_cfg.get("mongodb_uri", "mongodb://localhost:27017/")
    mongodb_database = db_cfg.get("mongodb_database", "western_armenian_corpus")

    try:
        from augmentation.metrics_pipeline import MetricsComputationPipeline
        from augmentation.metrics_visualization import (
            plot_metric_distribution,
            generate_analysis_report,
        )
        from augmentation.baseline_statistics import CorpusBaselineComputer
    except ImportError:
        from src.augmentation.metrics_pipeline import MetricsComputationPipeline
        from src.augmentation.metrics_visualization import (
            plot_metric_distribution,
            generate_analysis_report,
        )
        from src.augmentation.baseline_statistics import CorpusBaselineComputer

    try:
        from integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        from src.database.mongodb_client import MongoDBCorpusClient

    print("\n  Visualization (augmented metrics)\n")

    with MongoDBCorpusClient(uri=mongodb_uri, database_name=mongodb_database) as client:
        docs = client.find_documents(source="augmented", limit=args.limit)
        if not docs:
            print("  No augmented documents found. Run augmentation first.")
            return

        pipeline = MetricsComputationPipeline(mongodb_client=client)
        metric_cards = []
        for i, doc in enumerate(docs):
            text = doc.get("text") or ""
            if not text.strip():
                continue
            meta = doc.get("metadata") or {}
            strategy = meta.get("augmentation_strategy", "unknown")
            text_id = meta.get("task_uid", f"aug_{i}")
            card = pipeline.compute_augmented(
                text,
                text_id=text_id,
                source="augmented",
                strategy_name=strategy,
            )
            metric_cards.append(card)

        if not metric_cards:
            print("  No valid augmented texts for visualization.")
            return

        baseline_stats = None
        if args.baseline:
            computer = CorpusBaselineComputer()
            baseline_stats = computer.load_statistics(args.baseline)

        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)

        plot_path = plot_metric_distribution(
            metric_cards,
            args.metric,
            baseline_stats=baseline_stats,
            output_file=str(out_dir / f"{args.metric.replace('_', '-')}.png"),
            title=f"Distribution of {args.metric} (augmented)",
        )
        if plot_path:
            print(f"  Plot saved: {plot_path}")

        report = generate_analysis_report(
            metric_cards,
            baseline_stats=baseline_stats,
            output_file=str(out_dir / "analysis_report.json"),
        )
        print(f"  Report: {out_dir / 'analysis_report.json'} (num_texts={report['num_texts']})")
        print()


# ═══════════════════════════════════════════════════════════════════════
# Background launch (Windows-compatible)
# ═══════════════════════════════════════════════════════════════════════

def _launch_background() -> None:
    """Spawn a detached child process running the augmentation in foreground mode."""
    cmd = [sys.executable, "-m", "augmentation.runner", "run"]
    log_path = _ROOT / "data" / "augmented" / "augmentation.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict = {}
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW

    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(_ROOT),
            **kwargs,
        )

    print(f"\n  Augmentation launched in background (PID {proc.pid}).")
    print(f"  Logs:   {log_path}")
    print(f"  Status: python -m augmentation.runner status\n")


def _write_pid() -> None:
    pid_file = _pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))


def _remove_pid() -> None:
    try:
        _pid_file().unlink(missing_ok=True)
    except OSError:
        pass


_shutdown_requested = False


def _install_signal_handler() -> None:
    def handler(signum, frame):
        global _shutdown_requested
        if _shutdown_requested:
            sys.exit(1)
        _shutdown_requested = True
        logger.info("Shutdown requested — finishing current task then exiting …")
        print("\n  Shutdown requested — finishing current task …")

    signal.signal(signal.SIGINT, handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler)


# ═══════════════════════════════════════════════════════════════════════
# Hypothetical estimate (when no data exists yet)
# ═══════════════════════════════════════════════════════════════════════

def _show_hypothetical_estimate(
    llm_cfg: LLMConfig,
    worker_cfg: WorkerConfig,
    skip_benchmark: bool = False,
) -> None:
    """Print a hypothetical estimate based on expected data volumes."""
    print("  \u2500\u2500 Hypothetical estimates (based on expected scrape volumes) \u2500\u2500\n")

    avg_llm_sec = 20.0  # conservative default
    if not skip_benchmark:
        from augmentation.llm_client import LLMClient
        client = LLMClient(llm_cfg)
        try:
            if client.is_available():
                bench = client.benchmark(3)
                avg_llm_sec = bench["avg_seconds_per_request"]
                tps = bench["avg_tokens_per_sec"]
                print(f"  LLM benchmark: {tps:.1f} tok/s ({avg_llm_sec:.1f}s per request)\n")
            else:
                print(f"  LLM server not available \u2014 using conservative estimate ({avg_llm_sec:.0f}s/req)\n")
        except Exception:
            print(f"  LLM benchmark failed \u2014 using conservative estimate ({avg_llm_sec:.0f}s/req)\n")
    else:
        print(f"  Benchmark skipped \u2014 using conservative estimate ({avg_llm_sec:.0f}s/req)\n")

    # Expected data volumes from project documentation.
    scenarios = [
        ("Small scrape (~30MB clean text)",  5_000),
        ("Medium scrape (~80MB clean text)", 15_000),
        ("Full scrape (~150MB clean text)",  30_000),
    ]

    enabled_llm = sum(1 for s in ("paraphrase", "continue", "topic_write")
                      if worker_cfg.enabled_strategies.get(s, True))
    enabled_nonllm = sum(1 for s in ("sentence_shuffle", "random_deletion", "word_dropout")
                         if worker_cfg.enabled_strategies.get(s, True))

    # Average sample ratio across LLM strategies.
    avg_llm_ratio = 0.6  # (1.0 + 0.5 + 0.3) / 3
    avg_nonllm_ratio = 0.67

    for label, n_paras in scenarios:
        llm_tasks = int(n_paras * avg_llm_ratio * enabled_llm)
        nonllm_tasks = int(n_paras * avg_nonllm_ratio * enabled_nonllm)
        llm_hrs = (llm_tasks * avg_llm_sec) / 3600
        total_hrs = llm_hrs * 1.10  # +10% retry overhead
        days = total_hrs / 24

        print(f"  {label}:")
        print(f"    {n_paras:>6,} paragraphs → {llm_tasks:>6,} LLM + {nonllm_tasks:>6,} non-LLM tasks")
        print(f"    LLM time: {llm_hrs:>6.1f} hrs → Total: ~{total_hrs:.1f} hrs ({days:.1f} days)")
        print()


# ═══════════════════════════════════════════════════════════════════════
# Entry-point
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        prog="python -m augmentation.runner",
        description="WA data augmentation pipeline — local Llama 3.1 8B",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # estimate
    p_est = sub.add_parser("estimate", help="Show time estimate without running")
    p_est.add_argument("--skip-benchmark", action="store_true",
                       help="Skip LLM benchmark (use conservative defaults)")

    # run
    p_run = sub.add_parser("run", help="Run augmentation")
    p_run.add_argument("--background", action="store_true",
                       help="Launch as a detached background process")

    # status
    sub.add_parser("status", help="Show progress of running/completed augmentation")

    # metrics — post-augmentation metrics on MongoDB augmented output (MongoDB only, no local files)
    p_metrics = sub.add_parser("metrics", help="Compute metrics on augmented output; store in MongoDB only")
    p_metrics.add_argument("--limit", type=int, default=5000,
                           help="Max augmented documents to process (default: 5000)")

    # visualize — plot metric distributions from augmented docs or metric cards
    p_viz = sub.add_parser("visualize", help="Plot metric distributions and analysis (requires matplotlib)")
    p_viz.add_argument("--metric", default="lexical_ttr",
                       help="Metric to plot (e.g. lexical_ttr, quality_dialect_purity)")
    p_viz.add_argument("--output", default="cache/metric_plots",
                       help="Output directory for plots")
    p_viz.add_argument("--limit", type=int, default=1000,
                       help="Max augmented documents to load (default: 1000)")
    p_viz.add_argument("--baseline", default=None,
                       help="Path to baseline stats JSON (optional; e.g. cache/wa_metric_baseline_stats.json)")

    args = parser.parse_args()

    if args.command == "estimate":
        cmd_estimate(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "metrics":
        cmd_metrics(args)
    elif args.command == "visualize":
        cmd_visualize(args)


if __name__ == "__main__":
    main()
