"""Phase 2 always-on pipeline scheduler.

Provides a lightweight scheduler that runs pipeline stages on configurable
intervals with retry/backoff, state persistence, and basic alerting.

Usage
-----
Continuous foreground scheduler::

    python -m hytools.ingestion.runner schedule

Custom interval::

    python -m hytools.ingestion.runner schedule --interval 3600

With alerting::

    python -m hytools.ingestion.runner schedule --alert-file data/logs/alerts.jsonl

Design
------
- No external deps (no APScheduler/celery/etc.) — stdlib ``time.sleep`` loop.
- State persisted as JSON: last run time, per-stage status, consecutive fails.
- Retry with exponential backoff per stage (max 3 retries, 30/60/120s delays).
- Alert if no successful document ingestion for ``--alert-window`` seconds.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hytools.ingestion.runner import (
    _build_stages,
    _ensure_config,
    _resolve_log_dir,
    _run_stage,
    _write_pid,
    _remove_pid,
)

logger = logging.getLogger(__name__)

_STATE_FILENAME = "scheduler_state.json"
_ALERT_FILENAME = "alerts.jsonl"

DEFAULT_INTERVAL_SECONDS = 6 * 3600  # 6 hours
DEFAULT_ALERT_WINDOW_SECONDS = 24 * 3600  # 24 hours
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 30


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

@dataclass
class StageState:
    """Per-stage tracking across scheduler ticks."""

    name: str
    last_status: str = "never_run"
    last_run_iso: str = ""
    consecutive_failures: int = 0
    last_error: str = ""
    total_runs: int = 0
    total_failures: int = 0


@dataclass
class SchedulerState:
    """Global scheduler state persisted between ticks."""

    last_tick_iso: str = ""
    last_success_iso: str = ""
    total_ticks: int = 0
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "SchedulerState":
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                logger.debug("Corrupt scheduler state, starting fresh", exc_info=True)
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    def get_stage(self, name: str) -> StageState:
        raw = self.stages.get(name, {})
        return StageState(name=name, **{k: v for k, v in raw.items() if k in StageState.__dataclass_fields__ and k != "name"})

    def set_stage(self, ss: StageState) -> None:
        self.stages[ss.name] = asdict(ss)


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    severity: str  # "warning" | "critical"
    message: str
    timestamp_iso: str = ""
    context: dict[str, Any] = field(default_factory=dict)


def _emit_alert(alert: Alert, *, alert_file: Path | None = None) -> None:
    """Log an alert and optionally append to JSONL file."""
    alert.timestamp_iso = alert.timestamp_iso or datetime.now(timezone.utc).isoformat()
    if alert.severity == "critical":
        logger.critical("ALERT: %s", alert.message)
    else:
        logger.warning("ALERT: %s", alert.message)

    if alert_file:
        alert_file.parent.mkdir(parents=True, exist_ok=True)
        with open(alert_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(alert), ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def run_stage_with_retry(
    run_fn,
    stage_name: str,
    config: dict,
    *,
    max_retries: int = MAX_RETRIES,
) -> dict:
    """Run a single pipeline stage with exponential backoff on failure.

    Parameters
    ----------
    run_fn : callable
        Signature: ``(stage, config) -> dict`` (the ``_run_stage`` from runner).
    stage_name : str
        Human-readable stage name (for logging).
    config : dict
        Pipeline config dict.
    max_retries : int
        Max retry attempts after first failure.

    Returns
    -------
    dict
        Stage result record (same shape as ``_run_stage`` output).
    """
    config = _ensure_config(config)
    stages = _build_stages(config)
    stage = next((s for s in stages if s.name == stage_name), None)
    if stage is None:
        return {"stage": stage_name, "status": "unknown_stage", "error": f"Stage {stage_name!r} not found"}

    last_result: dict = {}
    for attempt in range(1 + max_retries):
        last_result = run_fn(stage, config)
        if last_result.get("status") == "ok":
            if attempt > 0:
                logger.info("Stage %s succeeded on retry %d", stage_name, attempt)
            return last_result

        if last_result.get("status") == "skipped":
            return last_result

        if attempt < max_retries:
            delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                "Stage %s failed (attempt %d/%d), retrying in %ds: %s",
                stage_name, attempt + 1, 1 + max_retries, delay,
                last_result.get("error", "")[:120],
            )
            time.sleep(delay)

    return last_result


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

def run_scheduler(
    config: dict,
    *,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    alert_window_seconds: int = DEFAULT_ALERT_WINDOW_SECONDS,
    alert_file: Path | None = None,
    state_dir: Path | None = None,
    only: list[str] | None = None,
    skip: list[str] | None = None,
    max_ticks: int | None = None,
) -> None:
    """Run the pipeline on a repeating schedule.

    Parameters
    ----------
    config : dict
        Full pipeline config (will be enriched via ``_ensure_config``).
    interval_seconds : int
        Seconds between pipeline ticks.
    alert_window_seconds : int
        If no stage succeeds within this window, emit a critical alert.
    alert_file : Path or None
        Append alerts as JSONL to this file.
    state_dir : Path or None
        Directory for scheduler state file (default: data/logs).
    only / skip : list[str] or None
        Stage filtering (same as ``run_pipeline``).
    max_ticks : int or None
        Stop after this many ticks (None = run forever). Useful for testing.
    """
    config = _ensure_config(config)
    log_dir = state_dir or _resolve_log_dir(config)
    state_path = log_dir / _STATE_FILENAME
    state = SchedulerState.load(state_path)

    _write_pid(log_dir)
    logger.info(
        "Pipeline scheduler started — interval=%ds, alert_window=%ds, ticks_so_far=%d",
        interval_seconds, alert_window_seconds, state.total_ticks,
    )

    tick = 0
    try:
        while max_ticks is None or tick < max_ticks:
            tick += 1
            now_iso = datetime.now(timezone.utc).isoformat()
            state.last_tick_iso = now_iso
            state.total_ticks += 1

            logger.info("=== Scheduler tick %d at %s ===", state.total_ticks, now_iso)

            stages = _build_stages(config)
            only_set = set(only or [])
            skip_set = set(skip or [])
            if only_set:
                for st in stages:
                    st.enabled = st.enabled and st.name in only_set
            if skip_set:
                for st in stages:
                    st.enabled = st.enabled and st.name not in skip_set

            any_ok = False
            for stage in stages:
                if not stage.enabled:
                    continue

                result = run_stage_with_retry(_run_stage, stage.name, config)
                ss = state.get_stage(stage.name)
                ss.last_status = result.get("status", "unknown")
                ss.last_run_iso = now_iso
                ss.total_runs += 1

                if result.get("status") == "ok":
                    ss.consecutive_failures = 0
                    ss.last_error = ""
                    any_ok = True
                elif result.get("status") == "failed":
                    ss.consecutive_failures += 1
                    ss.total_failures += 1
                    ss.last_error = result.get("error", "")[:200]

                    if ss.consecutive_failures >= 5:
                        _emit_alert(
                            Alert(
                                severity="warning",
                                message=f"Stage {stage.name} has failed {ss.consecutive_failures} consecutive times",
                                context={"stage": stage.name, "error": ss.last_error},
                            ),
                            alert_file=alert_file,
                        )

                state.set_stage(ss)

            if any_ok:
                state.last_success_iso = now_iso

            # Check staleness alert
            if state.last_success_iso:
                try:
                    last_ok = datetime.fromisoformat(state.last_success_iso)
                    now_dt = datetime.fromisoformat(now_iso)
                    gap = (now_dt - last_ok).total_seconds()
                    if gap > alert_window_seconds:
                        _emit_alert(
                            Alert(
                                severity="critical",
                                message=f"No successful ingestion for {gap / 3600:.1f} hours (threshold: {alert_window_seconds / 3600:.1f}h)",
                                context={"last_success": state.last_success_iso, "gap_seconds": gap},
                            ),
                            alert_file=alert_file,
                        )
                except ValueError:
                    pass

            state.save(state_path)
            logger.info(
                "Tick %d complete. Next tick in %ds. State saved to %s",
                state.total_ticks, interval_seconds, state_path,
            )

            if max_ticks is not None and tick >= max_ticks:
                break

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user (Ctrl+C)")
    finally:
        _remove_pid(log_dir)
        state.save(state_path)
        logger.info("Scheduler state saved. Total ticks: %d", state.total_ticks)
