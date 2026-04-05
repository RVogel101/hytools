"""Tests for the Phase 2 pipeline scheduler."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hytools.ingestion.scheduler import (
    Alert,
    SchedulerState,
    StageState,
    _emit_alert,
    run_stage_with_retry,
    run_scheduler,
    BACKOFF_BASE_SECONDS,
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_ALERT_WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# SchedulerState persistence
# ---------------------------------------------------------------------------


class TestSchedulerState:
    def test_load_missing_file(self, tmp_path: Path):
        state = SchedulerState.load(tmp_path / "nonexistent.json")
        assert state.total_ticks == 0
        assert state.last_tick_iso == ""
        assert state.stages == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        path = tmp_path / "state.json"
        state = SchedulerState(
            last_tick_iso="2026-01-01T00:00:00",
            last_success_iso="2026-01-01T00:00:00",
            total_ticks=5,
        )
        ss = StageState(name="wiki", last_status="ok", consecutive_failures=0, total_runs=3)
        state.set_stage(ss)
        state.save(path)

        loaded = SchedulerState.load(path)
        assert loaded.total_ticks == 5
        assert loaded.last_tick_iso == "2026-01-01T00:00:00"
        assert "wiki" in loaded.stages
        restored = loaded.get_stage("wiki")
        assert restored.last_status == "ok"
        assert restored.total_runs == 3

    def test_load_corrupt_file(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("NOT JSON", encoding="utf-8")
        state = SchedulerState.load(path)
        assert state.total_ticks == 0

    def test_get_stage_missing(self):
        state = SchedulerState()
        ss = state.get_stage("nonexistent")
        assert ss.name == "nonexistent"
        assert ss.last_status == "never_run"


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------


class TestAlerting:
    def test_emit_alert_to_file(self, tmp_path: Path):
        alert_file = tmp_path / "alerts.jsonl"
        alert = Alert(severity="warning", message="Test alert", context={"key": "val"})
        _emit_alert(alert, alert_file=alert_file)

        lines = alert_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["severity"] == "warning"
        assert data["message"] == "Test alert"
        assert data["timestamp_iso"] != ""

    def test_emit_alert_no_file(self):
        """Should not raise even without file."""
        alert = Alert(severity="critical", message="No file alert")
        _emit_alert(alert, alert_file=None)

    def test_emit_multiple_alerts(self, tmp_path: Path):
        alert_file = tmp_path / "alerts.jsonl"
        for i in range(3):
            _emit_alert(Alert(severity="warning", message=f"Alert {i}"), alert_file=alert_file)

        lines = alert_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    @patch("hytools.ingestion.scheduler.time.sleep")
    def test_succeeds_first_try(self, mock_sleep):
        mock_run = MagicMock(return_value={"stage": "wiki", "status": "ok"})

        with patch("hytools.ingestion.scheduler._build_stages") as mock_build, \
             patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c):
            from hytools.ingestion.runner import Stage
            mock_build.return_value = [Stage(name="wiki", module="dummy", enabled=True)]
            result = run_stage_with_retry(mock_run, "wiki", {})

        assert result["status"] == "ok"
        mock_sleep.assert_not_called()

    @patch("hytools.ingestion.scheduler.time.sleep")
    def test_retries_on_failure_then_succeeds(self, mock_sleep):
        results = [
            {"stage": "wiki", "status": "failed", "error": "timeout"},
            {"stage": "wiki", "status": "ok"},
        ]
        mock_run = MagicMock(side_effect=results)

        with patch("hytools.ingestion.scheduler._build_stages") as mock_build, \
             patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c):
            from hytools.ingestion.runner import Stage
            mock_build.return_value = [Stage(name="wiki", module="dummy", enabled=True)]
            result = run_stage_with_retry(mock_run, "wiki", {}, max_retries=2)

        assert result["status"] == "ok"
        assert mock_run.call_count == 2
        mock_sleep.assert_called_once_with(BACKOFF_BASE_SECONDS)

    @patch("hytools.ingestion.scheduler.time.sleep")
    def test_exhausts_retries(self, mock_sleep):
        mock_run = MagicMock(return_value={"stage": "wiki", "status": "failed", "error": "permanent"})

        with patch("hytools.ingestion.scheduler._build_stages") as mock_build, \
             patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c):
            from hytools.ingestion.runner import Stage
            mock_build.return_value = [Stage(name="wiki", module="dummy", enabled=True)]
            result = run_stage_with_retry(mock_run, "wiki", {}, max_retries=2)

        assert result["status"] == "failed"
        assert mock_run.call_count == 3  # 1 + 2 retries

    def test_unknown_stage(self):
        with patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c), \
             patch("hytools.ingestion.scheduler._build_stages", return_value=[]):
            result = run_stage_with_retry(lambda s, c: {}, "nonexistent_stage", {})
        assert result["status"] == "unknown_stage"

    @patch("hytools.ingestion.scheduler.time.sleep")
    def test_skipped_stage_no_retry(self, mock_sleep):
        mock_run = MagicMock(return_value={"stage": "wiki", "status": "skipped"})

        with patch("hytools.ingestion.scheduler._build_stages") as mock_build, \
             patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c):
            from hytools.ingestion.runner import Stage
            mock_build.return_value = [Stage(name="wiki", module="dummy", enabled=False)]
            result = run_stage_with_retry(mock_run, "wiki", {})

        assert result["status"] == "skipped"
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Scheduler loop (with max_ticks)
# ---------------------------------------------------------------------------


class TestSchedulerLoop:
    @patch("hytools.ingestion.scheduler.time.sleep")
    @patch("hytools.ingestion.scheduler._run_stage")
    @patch("hytools.ingestion.scheduler._build_stages")
    @patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c)
    @patch("hytools.ingestion.scheduler._resolve_log_dir")
    @patch("hytools.ingestion.scheduler._write_pid")
    @patch("hytools.ingestion.scheduler._remove_pid")
    def test_single_tick(self, mock_rmpid, mock_wpid, mock_logdir,
                         mock_ensure, mock_build, mock_run, mock_sleep,
                         tmp_path: Path):
        mock_logdir.return_value = tmp_path
        from hytools.ingestion.runner import Stage
        mock_build.return_value = [
            Stage(name="wiki", module="dummy", enabled=True),
        ]
        mock_run.return_value = {"stage": "wiki", "status": "ok", "duration_seconds": 1.0, "error": ""}

        run_scheduler({}, max_ticks=1, state_dir=tmp_path)

        assert (tmp_path / "scheduler_state.json").exists()
        state = SchedulerState.load(tmp_path / "scheduler_state.json")
        assert state.total_ticks == 1
        assert state.last_success_iso != ""
        assert "wiki" in state.stages
        assert state.stages["wiki"]["last_status"] == "ok"

    @patch("hytools.ingestion.scheduler.time.sleep")
    @patch("hytools.ingestion.scheduler._run_stage")
    @patch("hytools.ingestion.scheduler._build_stages")
    @patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c)
    @patch("hytools.ingestion.scheduler._resolve_log_dir")
    @patch("hytools.ingestion.scheduler._write_pid")
    @patch("hytools.ingestion.scheduler._remove_pid")
    def test_staleness_alert(self, mock_rmpid, mock_wpid, mock_logdir,
                             mock_ensure, mock_build, mock_run, mock_sleep,
                             tmp_path: Path):
        """If last_success_iso is old enough, a staleness alert is emitted."""
        mock_logdir.return_value = tmp_path
        from hytools.ingestion.runner import Stage
        mock_build.return_value = [
            Stage(name="wiki", module="dummy", enabled=True),
        ]
        # Stage always fails
        mock_run.return_value = {"stage": "wiki", "status": "failed", "error": "down", "duration_seconds": 0}

        # Pre-seed state with an old success timestamp
        old_state = SchedulerState(last_success_iso="2020-01-01T00:00:00+00:00")
        old_state.save(tmp_path / "scheduler_state.json")

        alert_file = tmp_path / "alerts.jsonl"
        run_scheduler({}, max_ticks=1, state_dir=tmp_path,
                      alert_file=alert_file, alert_window_seconds=3600)

        assert alert_file.exists()
        lines = alert_file.read_text(encoding="utf-8").strip().split("\n")
        assert any("No successful ingestion" in line for line in lines)

    @patch("hytools.ingestion.scheduler.time.sleep")
    @patch("hytools.ingestion.scheduler._run_stage")
    @patch("hytools.ingestion.scheduler._build_stages")
    @patch("hytools.ingestion.scheduler._ensure_config", side_effect=lambda c: c)
    @patch("hytools.ingestion.scheduler._resolve_log_dir")
    @patch("hytools.ingestion.scheduler._write_pid")
    @patch("hytools.ingestion.scheduler._remove_pid")
    def test_consecutive_failure_alert(self, mock_rmpid, mock_wpid, mock_logdir,
                                       mock_ensure, mock_build, mock_run, mock_sleep,
                                       tmp_path: Path):
        """After 5 consecutive fails, a stage-specific alert fires."""
        mock_logdir.return_value = tmp_path
        from hytools.ingestion.runner import Stage
        mock_build.return_value = [
            Stage(name="wiki", module="dummy", enabled=True),
        ]
        mock_run.return_value = {"stage": "wiki", "status": "failed", "error": "broken", "duration_seconds": 0}

        # Pre-seed state with 4 consecutive failures (this tick will be the 5th)
        old_state = SchedulerState(last_success_iso="2026-01-01T00:00:00+00:00")
        ss = StageState(name="wiki", consecutive_failures=4, total_runs=4, total_failures=4)
        old_state.set_stage(ss)
        old_state.save(tmp_path / "scheduler_state.json")

        alert_file = tmp_path / "alerts.jsonl"
        run_scheduler({}, max_ticks=1, state_dir=tmp_path, alert_file=alert_file)

        assert alert_file.exists()
        lines = alert_file.read_text(encoding="utf-8").strip().split("\n")
        assert any("5 consecutive" in line for line in lines)
