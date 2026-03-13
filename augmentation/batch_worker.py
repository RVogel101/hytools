"""Core batch processing engine with checkpointing and progress tracking.

Scans source documents, segments them into paragraphs, builds a task
queue, processes tasks through strategies, and writes results — all with
resume support via a JSONL checkpoint file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from augmentation.llm_client import LLMClient, LLMConfig
from augmentation.strategies import Strategy, build_strategies
from integrations.database.mongodb_client import MongoDBCorpusClient

logger = logging.getLogger(__name__)

# Minimum Armenian character ratio for a paragraph to be worth augmenting.
_MIN_ARM_RATIO = 0.50
_ARM_RE = re.compile(r"[\u0531-\u0587\uFB13-\uFB17]")


# ═══════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Paragraph:
    """A single paragraph extracted from a source document."""
    doc_path: str          # relative path of the source .txt file
    index: int             # paragraph index within the document
    text: str
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.text)

    @property
    def uid(self) -> str:
        """Deterministic unique id for checkpoint dedup."""
        raw = f"{self.doc_path}::{self.index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class Task:
    """One (paragraph, strategy) pair to execute."""
    paragraph: Paragraph
    strategy_name: str

    @property
    def uid(self) -> str:
        return f"{self.paragraph.uid}_{self.strategy_name}"


@dataclass
class TaskResult:
    task_uid: str
    strategy: str
    source_doc: str
    paragraph_index: int
    success: bool
    output_text: str = ""
    duration_seconds: float = 0.0
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Document scanner
# ═══════════════════════════════════════════════════════════════════════

def scan_documents(
    source_dir: Path,
    min_paragraph_chars: int = 100,
    max_paragraph_chars: int = 3000,
    min_armenian_ratio: float = 0.50,
) -> list[Paragraph]:
    """Read all .txt files from *source_dir* and extract paragraphs."""
    paragraphs: list[Paragraph] = []
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        logger.warning("Source directory does not exist: %s", source_dir)
        return paragraphs

    txt_files = sorted(source_dir.rglob("*.txt"))
    logger.info("Found %d .txt files in %s", len(txt_files), source_dir)

    for fpath in txt_files:
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", fpath, exc)
            continue

        rel = fpath.relative_to(source_dir).as_posix()
        for i, para in enumerate(_split_paragraphs(content)):
            if len(para) < min_paragraph_chars:
                continue
            if len(para) > max_paragraph_chars:
                para = para[:max_paragraph_chars]
            arm_chars = len(_ARM_RE.findall(para))
            if arm_chars / len(para) < min_armenian_ratio:
                continue
            paragraphs.append(Paragraph(doc_path=rel, index=i, text=para))

    logger.info("Extracted %d paragraphs from %d documents", len(paragraphs), len(txt_files))
    return paragraphs


def scan_documents_from_mongodb(
    mongodb_uri: str,
    mongodb_database: str,
    source_filter: Optional[str] = None,
    max_documents: Optional[int] = None,
    min_paragraph_chars: int = 100,
    max_paragraph_chars: int = 3000,
    min_armenian_ratio: float = 0.50,
) -> list[Paragraph]:
    """Read MongoDB documents and extract valid Armenian paragraphs."""
    paragraphs: list[Paragraph] = []

    with MongoDBCorpusClient(uri=mongodb_uri, database_name=mongodb_database) as client:
        query: dict = {}
        if source_filter:
            query["source"] = source_filter

        cursor = client.documents.find(query, {"_id": 1, "source": 1, "title": 1, "text": 1})
        if max_documents and max_documents > 0:
            cursor = cursor.limit(max_documents)

        docs = list(cursor)
        logger.info(
            "Found %d MongoDB documents in %s (source_filter=%s)",
            len(docs),
            mongodb_database,
            source_filter or "none",
        )

        for doc in docs:
            content = (doc.get("text") or "").strip()
            if not content:
                continue

            source = str(doc.get("source") or "unknown")
            title = str(doc.get("title") or "untitled")
            doc_path = f"mongo://{source}/{title}::{doc.get('_id')}"

            for i, para in enumerate(_split_paragraphs(content)):
                if len(para) < min_paragraph_chars:
                    continue
                if len(para) > max_paragraph_chars:
                    para = para[:max_paragraph_chars]
                arm_chars = len(_ARM_RE.findall(para))
                if arm_chars / len(para) < min_armenian_ratio:
                    continue
                paragraphs.append(Paragraph(doc_path=doc_path, index=i, text=para))

    logger.info("Extracted %d paragraphs from MongoDB source", len(paragraphs))
    return paragraphs


def _split_paragraphs(text: str) -> list[str]:
    """Split text on blank lines, return non-empty paragraphs."""
    blocks = re.split(r"\n\s*\n", text)
    return [b.strip() for b in blocks if b.strip()]


# ═══════════════════════════════════════════════════════════════════════
# Checkpoint manager
# ═══════════════════════════════════════════════════════════════════════

class Checkpoint:
    """Checkpoint for tracking completed tasks. Uses file or MongoDB based on backend."""

    def __init__(self, path: Path, mongodb_client: Optional[Any] = None) -> None:
        self.path = Path(path)
        self._mongodb = mongodb_client
        self._completed: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._mongodb is not None:
            try:
                self._completed = self._mongodb.load_augmentation_checkpoint_uids()
                logger.info("Checkpoint loaded from MongoDB: %d completed tasks", len(self._completed))
            except Exception as exc:
                logger.warning("Could not load checkpoint from MongoDB: %s", exc)
            return
        if self.path.is_file():
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        self._completed.add(rec["task_uid"])
                    except (json.JSONDecodeError, KeyError):
                        continue
            logger.info("Checkpoint loaded: %d completed tasks", len(self._completed))

    def is_done(self, task_uid: str) -> bool:
        return task_uid in self._completed

    def mark_done(self, result: TaskResult) -> None:
        self._completed.add(result.task_uid)
        rec = {
            "task_uid": result.task_uid,
            "strategy": result.strategy,
            "source_doc": result.source_doc,
            "paragraph_index": result.paragraph_index,
            "success": result.success,
            "duration_seconds": round(result.duration_seconds, 3),
            "error": result.error,
            "timestamp": time.time(),
        }
        if self._mongodb is not None:
            try:
                self._mongodb.mark_augmentation_done(result.task_uid, rec)
            except Exception as exc:
                logger.warning("Could not save checkpoint to MongoDB: %s", exc)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @property
    def completed_count(self) -> int:
        return len(self._completed)


# ═══════════════════════════════════════════════════════════════════════
# Batch worker
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class WorkerConfig:
    source_backend: str = "filesystem"  # filesystem | mongodb
    output_backend: str = "mongodb"  # mongodb only — filesystem output disabled
    source_dir: Path = Path("data/cleaned")
    mongodb_uri: str = "mongodb://localhost:27017/"
    mongodb_database: str = "western_armenian_corpus"
    mongodb_source_filter: str = ""
    mongodb_max_documents: int = 0  # 0 = unlimited
    allow_filesystem_fallback: bool = True
    output_dir: Path = Path("data/augmented")
    checkpoint_file: Path = Path("data/augmented/.checkpoint.jsonl")
    log_file: Path = Path("data/augmented/augmentation.log")
    log_dir: Path | None = None  # When output_backend=mongodb, summary and logs go here (zero local storage)
    use_safe_wrapper: bool = False  # Wrap LLM strategies in SafeAugmentationWrapper for stricter WA guarantees
    min_paragraph_chars: int = 100
    max_paragraph_chars: int = 3000
    min_armenian_ratio: float = 0.70
    validate_wa_output: bool = True
    
    # Validation retry settings
    max_retries: int = 3
    strict_classical: bool = True
    check_nayiri: bool = False
    
    # Per-strategy sample ratios (fraction of paragraphs to process).
    sample_ratios: dict[str, float] = field(default_factory=lambda: {
        "paraphrase": 1.0,
        "continue": 0.5,
        "topic_write": 0.3,
        "sentence_shuffle": 1.0,
        "random_deletion": 0.5,
        "word_dropout": 0.5,
    })
    # Which strategies are enabled.
    enabled_strategies: dict[str, bool] = field(default_factory=lambda: {
        "paraphrase": True,
        "continue": True,
        "topic_write": True,
        "sentence_shuffle": True,
        "random_deletion": True,
        "word_dropout": True,
    })
    # When True, run MetricsComputationPipeline.compute_baseline and compute_augmented
    # after each successful task and store in MongoDB.
    compute_metrics_per_task: bool = False


class BatchWorker:
    """Processes augmentation tasks in batches with full checkpoint/resume."""

    def __init__(
        self,
        worker_config: WorkerConfig,
        llm_config: LLMConfig | None = None,
    ) -> None:
        self.cfg = worker_config
        self.llm_config = llm_config or LLMConfig()
        self._mongo_client: Any = None
        use_mongo = (self.cfg.output_backend or "filesystem").strip().lower() == "mongodb"
        if use_mongo:
            try:
                self._mongo_client = MongoDBCorpusClient(
                    uri=self.cfg.mongodb_uri,
                    database_name=self.cfg.mongodb_database,
                )
                self._mongo_client.connect()
            except Exception as exc:
                logger.warning("MongoDB output unavailable: %s — using file checkpoint/output", exc)
                self._mongo_client = None
        self.checkpoint = Checkpoint(
            self.cfg.checkpoint_file,
            mongodb_client=self._mongo_client,
        )
        self._stats = {"total": 0, "completed": 0, "skipped_checkpoint": 0,
                       "success": 0, "failed": 0, "skipped_validation": 0}

    def build_task_queue(self) -> list[Task]:
        """Scan source data and build the full list of tasks."""
        backend = (self.cfg.source_backend or "filesystem").strip().lower()
        paragraphs: list[Paragraph] = []

        if backend == "mongodb":
            try:
                paragraphs = scan_documents_from_mongodb(
                    mongodb_uri=self.cfg.mongodb_uri,
                    mongodb_database=self.cfg.mongodb_database,
                    source_filter=self.cfg.mongodb_source_filter or None,
                    max_documents=(self.cfg.mongodb_max_documents or None),
                    min_paragraph_chars=self.cfg.min_paragraph_chars,
                    max_paragraph_chars=self.cfg.max_paragraph_chars,
                    min_armenian_ratio=self.cfg.min_armenian_ratio,
                )
            except Exception as exc:
                logger.error("MongoDB source scan failed: %s", exc)
                if self.cfg.allow_filesystem_fallback:
                    logger.warning("Falling back to filesystem source: %s", self.cfg.source_dir)
                    paragraphs = scan_documents(
                        self.cfg.source_dir,
                        min_paragraph_chars=self.cfg.min_paragraph_chars,
                        max_paragraph_chars=self.cfg.max_paragraph_chars,
                        min_armenian_ratio=self.cfg.min_armenian_ratio,
                    )
                else:
                    raise
        else:
            paragraphs = scan_documents(
                self.cfg.source_dir,
                min_paragraph_chars=self.cfg.min_paragraph_chars,
                max_paragraph_chars=self.cfg.max_paragraph_chars,
                min_armenian_ratio=self.cfg.min_armenian_ratio,
            )

        if not paragraphs:
            logger.warning("No paragraphs found — check source backend '%s' and input data.", backend)
            return []

        tasks: list[Task] = []
        for strat_name, enabled in self.cfg.enabled_strategies.items():
            if not enabled:
                continue
            ratio = self.cfg.sample_ratios.get(strat_name, 1.0)
            n = max(1, int(len(paragraphs) * ratio))
            selected = paragraphs[:n] if ratio >= 1.0 else _sample(paragraphs, n)
            for para in selected:
                tasks.append(Task(paragraph=para, strategy_name=strat_name))

        logger.info("Built %d tasks across %d strategies from %d paragraphs",
                     len(tasks), sum(v for v in self.cfg.enabled_strategies.values()), len(paragraphs))
        return tasks

    def run(self, tasks: list[Task] | None = None) -> dict:
        """Execute all tasks, writing results to disk.

        Returns summary statistics dict.
        """
        if tasks is None:
            tasks = self.build_task_queue()

        self._stats["total"] = len(tasks)

        # Separate LLM and non-LLM tasks so we can skip LLM init if not needed.
        llm_needed = any(t.strategy_name in ("paraphrase", "continue", "topic_write") for t in tasks)
        llm_client: LLMClient | None = None
        if llm_needed:
            llm_client = LLMClient(self.llm_config)
            if not llm_client.is_available():
                logger.error("LLM server not reachable at %s — LLM tasks will be skipped. "
                             "Start Ollama and retry.", self.llm_config.base_url)
                llm_client = None

        strategies = build_strategies(
            llm_client,
            validate_wa=self.cfg.validate_wa_output,
            max_retries=self.cfg.max_retries,
            strict_classical=self.cfg.strict_classical,
            check_nayiri=self.cfg.check_nayiri,
            enabled=self.cfg.enabled_strategies,
        )
        if self.cfg.use_safe_wrapper:
            from augmentation.safe_generation import SafeAugmentationWrapper
            wrapped = []
            for s in strategies:
                if getattr(s, "requires_llm", False):
                    wrapped.append(SafeAugmentationWrapper(s, max_attempts=5, min_confidence=0.85))
                else:
                    wrapped.append(s)
            strategies = wrapped
        strat_map = {getattr(s, "name", "unknown"): s for s in strategies}

        use_mongo_out = (self.cfg.output_backend or "mongodb").strip().lower() == "mongodb"
        if use_mongo_out and self._mongo_client is None:
            raise RuntimeError(
                "Augmentation requires MongoDB output but connection failed. "
                "Ensure MongoDB is running and database.mongodb_uri is correct."
            )
        if not use_mongo_out:
            raise RuntimeError("Augmentation output_backend must be 'mongodb'. Filesystem output is disabled.")
        self._setup_file_logging()

        # Main processing loop.
        with tqdm(total=len(tasks), desc="Augmenting", unit="task") as pbar:
            for task in tasks:
                # Skip if already completed in a previous run.
                if self.checkpoint.is_done(task.uid):
                    self._stats["skipped_checkpoint"] += 1
                    pbar.update(1)
                    continue

                strat = strat_map.get(task.strategy_name)
                if strat is None:
                    # Strategy disabled or LLM unavailable.
                    pbar.update(1)
                    continue

                result = self._execute_task(task, strat)
                self.checkpoint.mark_done(result)

                if result.success and result.output_text:
                    self._write_output(task, result.output_text)
                    self._stats["success"] += 1
                    if self.cfg.compute_metrics_per_task and self._mongo_client is not None:
                        try:
                            from augmentation.metrics_pipeline import MetricsComputationPipeline
                            pipeline = MetricsComputationPipeline(mongodb_client=self._mongo_client)
                            pipeline.compute_baseline(
                                task.paragraph.text,
                                text_id=task.uid + "_orig",
                                source="augmented_original",
                            )
                            pipeline.compute_augmented(
                                result.output_text,
                                original_text=task.paragraph.text,
                                text_id=task.uid,
                                source="augmented",
                                strategy_name=task.strategy_name,
                            )
                        except Exception as exc:
                            logger.warning("Per-task metrics failed for %s: %s", task.uid, exc)
                elif not result.success:
                    self._stats["failed"] += 1
                else:
                    self._stats["skipped_validation"] += 1

                self._stats["completed"] += 1
                pbar.set_postfix(ok=self._stats["success"], fail=self._stats["failed"])
                pbar.update(1)

        self._write_summary()
        if self._mongo_client is not None:
            self._mongo_client.close()
            self._mongo_client = None
        return self._stats

    def _execute_task(self, task: Task, strategy: Strategy) -> TaskResult:
        t0 = time.monotonic()
        try:
            output = strategy(task.paragraph.text)
            elapsed = time.monotonic() - t0
            if output is None:
                return TaskResult(
                    task_uid=task.uid, strategy=task.strategy_name,
                    source_doc=task.paragraph.doc_path,
                    paragraph_index=task.paragraph.index,
                    success=True, output_text="", duration_seconds=elapsed,
                )
            return TaskResult(
                task_uid=task.uid, strategy=task.strategy_name,
                source_doc=task.paragraph.doc_path,
                paragraph_index=task.paragraph.index,
                success=True, output_text=output, duration_seconds=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Task %s failed: %s", task.uid, exc)
            return TaskResult(
                task_uid=task.uid, strategy=task.strategy_name,
                source_doc=task.paragraph.doc_path,
                paragraph_index=task.paragraph.index,
                success=False, duration_seconds=elapsed, error=str(exc),
            )

    def _write_output(self, task: Task, text: str) -> None:
        """Write augmented text to MongoDB only (no filesystem fallback)."""
        use_mongo = (self.cfg.output_backend or "filesystem").strip().lower() == "mongodb"
        if use_mongo and self._mongo_client is not None:
            try:
                self._mongo_client.insert_augmented_document(
                    source_doc=task.paragraph.doc_path,
                    strategy=task.strategy_name,
                    text=text,
                    paragraph_index=task.paragraph.index,
                    task_uid=task.uid,
                )
            except Exception as exc:
                logger.error("MongoDB insert failed for %s: %s — output lost (MongoDB-only mode)", task.uid, exc)
                raise
        else:
            raise RuntimeError(
                "Augmentation output_backend must be 'mongodb'. "
                "Filesystem output is disabled. Set database.use_mongodb and augmentation.output_backend."
            )

    def _write_summary(self) -> None:
        use_mongo = (self.cfg.output_backend or "filesystem").strip().lower() == "mongodb"
        if use_mongo and self.cfg.log_dir:
            summary_path = self.cfg.log_dir / "augmentation_summary.json"
        elif use_mongo:
            logger.info("Augmentation complete. Stats: %s", self._stats)
            return
        else:
            summary_path = self.cfg.output_dir / "summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self._stats, f, indent=2)
        logger.info("Augmentation complete. Stats: %s", self._stats)

    def _setup_file_logging(self) -> None:
        self.cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(self.cfg.log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger("src.augmentation").addHandler(fh)


def _sample(items: list, n: int) -> list:
    """Deterministic sample *n* items (seeded for reproducibility)."""
    rng = random.Random(42)
    if n >= len(items):
        return items[:]
    return rng.sample(items, n)


# ═══════════════════════════════════════════════════════════════════════
# Time estimator
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TimeEstimate:
    """Result of a time-estimation run."""
    total_paragraphs: int
    total_tasks: int
    llm_tasks: int
    non_llm_tasks: int
    benchmark: dict                     # from LLMClient.benchmark()
    avg_seconds_per_llm_task: float
    llm_hours: float
    non_llm_seconds: float
    retry_overhead_pct: float
    total_hours: float
    expected_output_mb: float
    per_strategy: dict[str, dict]       # strategy_name -> {tasks, hours}
    already_completed: int

    def display(self) -> str:
        lines = [
            "",
            "=" * 66,
            "  WA Data Augmentation — Time Estimate",
            "=" * 66,
            "",
            f"  Source paragraphs:     {self.total_paragraphs:>8,}",
            f"  Total tasks:           {self.total_tasks:>8,}",
            f"  Already completed:     {self.already_completed:>8,}",
            f"  Remaining tasks:       {self.total_tasks - self.already_completed:>8,}",
            "",
        ]
        if self.benchmark.get("samples", 0) > 0:
            lines += [
                f"  LLM benchmark:         {self.benchmark['avg_tokens_per_sec']:.1f} tok/s "
                f"({self.benchmark['avg_seconds_per_request']:.1f}s/req)",
                f"  LLM model:             local Llama 3.1 8B",
            ]
        else:
            lines += [
                "  LLM benchmark:         (server unavailable — using estimates)",
            ]
        lines += [
            "",
            "  ── Per strategy ─────────────────────────────────────────",
        ]
        for name, info in self.per_strategy.items():
            hrs = info["hours"]
            if hrs < 0.02:
                time_str = f"{info['seconds']:.0f} seconds"
            else:
                time_str = f"{hrs:.1f} hours"
            lines.append(f"  {name:<22} {info['tasks']:>6,} tasks  →  {time_str}")

        lines += [
            "",
            "  ── Totals ───────────────────────────────────────────────",
            f"  LLM tasks time:        {self.llm_hours:>8.1f} hours",
            f"  Non-LLM tasks time:    {self.non_llm_seconds:>8.0f} seconds",
            f"  Retry overhead (+{self.retry_overhead_pct:.0f}%): {self.total_hours - (self.llm_hours + self.non_llm_seconds/3600):>8.1f} hours",
            f"  ─────────────────────────────────────",
            f"  ESTIMATED TOTAL:       {self.total_hours:>8.1f} hours  ({self.total_hours / 24:.1f} days)",
            f"  Expected output:       ~{self.expected_output_mb:.1f} MB additional WA text",
            "",
            "=" * 66,
            "",
        ]
        return "\n".join(lines)


def estimate_time(
    worker_config: WorkerConfig,
    llm_config: LLMConfig | None = None,
    retry_overhead_pct: float = 10.0,
    run_benchmark: bool = True,
) -> TimeEstimate:
    """Estimate total augmentation time without running anything.

    If *run_benchmark* is True and the LLM server is reachable, runs a
    quick benchmark to measure actual inference speed.
    """
    backend = (worker_config.source_backend or "filesystem").strip().lower()
    paragraphs: list[Paragraph] = []

    if backend == "mongodb":
        try:
            paragraphs = scan_documents_from_mongodb(
                mongodb_uri=worker_config.mongodb_uri,
                mongodb_database=worker_config.mongodb_database,
                source_filter=worker_config.mongodb_source_filter or None,
                max_documents=(worker_config.mongodb_max_documents or None),
                min_paragraph_chars=worker_config.min_paragraph_chars,
                max_paragraph_chars=worker_config.max_paragraph_chars,
                min_armenian_ratio=worker_config.min_armenian_ratio,
            )
        except Exception as exc:
            logger.error("MongoDB source scan failed during estimate: %s", exc)
            if worker_config.allow_filesystem_fallback:
                logger.warning("Falling back to filesystem source for estimate: %s", worker_config.source_dir)
                paragraphs = scan_documents(
                    worker_config.source_dir,
                    min_paragraph_chars=worker_config.min_paragraph_chars,
                    max_paragraph_chars=worker_config.max_paragraph_chars,
                    min_armenian_ratio=worker_config.min_armenian_ratio,
                )
            else:
                raise
    else:
        paragraphs = scan_documents(
            worker_config.source_dir,
            min_paragraph_chars=worker_config.min_paragraph_chars,
            max_paragraph_chars=worker_config.max_paragraph_chars,
            min_armenian_ratio=worker_config.min_armenian_ratio,
        )

    checkpoint = Checkpoint(worker_config.checkpoint_file)

    # Build task counts per strategy.
    llm_strats = {"paraphrase", "continue", "topic_write"}
    per_strategy: dict[str, dict] = {}
    total_llm = 0
    total_nonllm = 0

    for strat_name, enabled in worker_config.enabled_strategies.items():
        if not enabled:
            continue
        ratio = worker_config.sample_ratios.get(strat_name, 1.0)
        n_tasks = max(1, int(len(paragraphs) * ratio)) if paragraphs else 0
        per_strategy[strat_name] = {"tasks": n_tasks, "is_llm": strat_name in llm_strats}
        if strat_name in llm_strats:
            total_llm += n_tasks
        else:
            total_nonllm += n_tasks

    # Benchmark LLM speed.
    bench: dict = {"avg_tokens_per_sec": 8.0, "avg_seconds_per_request": 20.0, "samples": 0}
    if run_benchmark and total_llm > 0:
        cfg = llm_config or LLMConfig()
        client = LLMClient(cfg)
        if client.is_available():
            bench = client.benchmark(n_samples=3)

    avg_sec_llm = bench["avg_seconds_per_request"]
    avg_sec_nonllm = 0.005  # ~5ms per non-LLM transform

    # Per-strategy time.
    for name, info in per_strategy.items():
        sec = info["tasks"] * (avg_sec_llm if info["is_llm"] else avg_sec_nonllm)
        info["seconds"] = sec
        info["hours"] = sec / 3600

    llm_hours = (total_llm * avg_sec_llm) / 3600
    nonllm_sec = total_nonllm * avg_sec_nonllm
    raw_hours = llm_hours + nonllm_sec / 3600
    total_hours = raw_hours * (1 + retry_overhead_pct / 100)

    # Rough output size estimate: avg 500 chars per generation.
    avg_output_chars = 500
    total_tasks = total_llm + total_nonllm
    expected_mb = (total_tasks * avg_output_chars) / (1024 * 1024)

    return TimeEstimate(
        total_paragraphs=len(paragraphs),
        total_tasks=total_tasks,
        llm_tasks=total_llm,
        non_llm_tasks=total_nonllm,
        benchmark=bench,
        avg_seconds_per_llm_task=avg_sec_llm,
        llm_hours=llm_hours,
        non_llm_seconds=nonllm_sec,
        retry_overhead_pct=retry_overhead_pct,
        total_hours=total_hours,
        expected_output_mb=expected_mb,
        per_strategy=per_strategy,
        already_completed=checkpoint.completed_count,
    )
