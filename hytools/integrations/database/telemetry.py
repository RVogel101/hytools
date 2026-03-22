"""Process telemetry and comprehensive logging system."""

import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import uuid

from .connection import DatabaseConnection

logger = logging.getLogger(__name__)


class ProcessTelemetry:
    """Records and tracks detailed process metrics, bottlenecks, and events."""

    def __init__(self, db: DatabaseConnection):
        """Initialize telemetry recorder.
        
        Args:
            db: DatabaseConnection instance
        """
        self.db = db
        self._active_operations: Dict[str, dict] = {}
        self._phase_timers: Dict[str, float] = {}

    def start_operation(
        self,
        source_type: str,
        source_name: str,
        description: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> str:
        """Start tracking a new scraping/ingestion operation.
        
        Args:
            source_type: Type of source (newspaper, nayiri, archive_org, etc.)
            source_name: Name of specific source
            description: Optional operation description
            config: Config snapshot for audit
            
        Returns:
            operation_id for use in subsequent telemetry calls
        """
        operation_id = self.db.start_ingestion_operation(
            source_type=source_type,
            source_name=source_name,
            description=description,
            config_snapshot=config,
        )

        self._active_operations[operation_id] = {
            "source_type": source_type,
            "source_name": source_name,
            "start_time": time.time(),
            "phase_start_times": {},
            "records_attempted": 0,
            "records_imported": 0,
            "records_skipped": 0,
            "records_failed": 0,
            "issues": [],
        }

        logger.info(f"Started operation {operation_id}: {source_type}/{source_name}")
        return operation_id

    def end_operation(self, operation_id: str, status: str = "success", error: Optional[str] = None):
        """Mark operation as complete and record final metrics.
        
        Args:
            operation_id: Operation to finalize
            status: Final status (success, partial, failed)
            error: Optional error message
        """
        if operation_id not in self._active_operations:
            logger.warning(f"No active operation tracked: {operation_id}")
            return

        op_data = self._active_operations[operation_id]
        duration = time.time() - op_data["start_time"]

        self.db.end_ingestion_operation(operation_id, status, error)

        # Record final metrics
        metrics_id = str(uuid.uuid4())
        sql = """
        INSERT INTO process_metrics (
            metrics_id, operation_id, source_type, source_name,
            total_records_attempted, total_records_imported, total_records_skipped,
            total_records_failed, total_duration_seconds, avg_record_time_ms,
            earliest_timestamp, latest_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-' || ? || ' seconds'), datetime('now'))
        """
        total_records = op_data["records_attempted"]
        avg_time_ms = (duration * 1000 / max(total_records, 1)) if total_records > 0 else 0

        self.db.execute(
            sql,
            (
                metrics_id,
                operation_id,
                op_data["source_type"],
                op_data["source_name"],
                total_records,
                op_data["records_imported"],
                op_data["records_skipped"],
                op_data["records_failed"],
                duration,
                avg_time_ms,
                int(duration),
            ),
        )
        self.db.commit()

        logger.info(
            f"Ended operation {operation_id}: {status} "
            f"({op_data['records_imported']}/{total_records} records, {duration:.1f}s)"
        )

        del self._active_operations[operation_id]

    def start_phase(self, operation_id: str, phase_name: str):
        """Mark the start of a process phase (e.g., extraction, dedup, ingestion)."""
        self._phase_timers[f"{operation_id}_{phase_name}"] = time.time()
        logger.debug(f"Phase started: {phase_name}")

    def end_phase(self, operation_id: str, phase_name: str, record_count: Optional[int] = None):
        """Mark the end of a process phase and record duration."""
        timer_key = f"{operation_id}_{phase_name}"
        if timer_key not in self._phase_timers:
            logger.warning(f"No start time for phase: {phase_name}")
            return

        duration = time.time() - self._phase_timers[timer_key]
        del self._phase_timers[timer_key]

        telemetry_id = str(uuid.uuid4())
        sql = """
        INSERT INTO process_telemetry (
            telemetry_id, operation_id, source_type, source_name,
            process_phase, event_type, event_description, duration_seconds, success
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        if operation_id in self._active_operations:
            op_data = self._active_operations[operation_id]
            self.db.execute(
                sql,
                (
                    telemetry_id,
                    operation_id,
                    op_data["source_type"],
                    op_data["source_name"],
                    phase_name,
                    "phase_complete",
                    f"Phase {phase_name} completed" + (f" ({record_count} records)" if record_count else ""),
                    duration,
                    True,
                ),
            )
            self.db.commit()

        logger.debug(f"Phase ended: {phase_name} ({duration:.1f}s)")

    def record_metric(
        self,
        operation_id: str,
        metric_name: str,
        metric_value: float,
        unit: str = "",
        phase: Optional[str] = None,
    ):
        """Record a specific metric for the operation.
        
        Args:
            operation_id: Operation to record metric for
            metric_name: Name of metric (e.g., 'extraction_rate', 'dedup_matches')
            metric_value: Value of metric
            unit: Unit of measurement (e.g., 'records/sec', '%', 'ms')
            phase: Optional phase name
        """
        telemetry_id = str(uuid.uuid4())
        sql = """
        INSERT INTO process_telemetry (
            telemetry_id, operation_id, source_type, source_name,
            process_phase, event_type, metric_name, metric_value, metric_unit, success
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        if operation_id in self._active_operations:
            op_data = self._active_operations[operation_id]
            self.db.execute(
                sql,
                (
                    telemetry_id,
                    operation_id,
                    op_data["source_type"],
                    op_data["source_name"],
                    phase,
                    "metric",
                    metric_name,
                    metric_value,
                    unit,
                    True,
                ),
            )
            self.db.commit()

        logger.debug(f"Metric recorded: {metric_name}={metric_value}{unit}")

    def record_issue(
        self,
        operation_id: str,
        issue_category: str,
        description: str,
        severity: str = "warning",
        affected_records: int = 0,
        affected_items: Optional[str] = None,
        resolution_attempted: Optional[str] = None,
        resolution_success: bool = False,
    ):
        """Record a bottleneck, issue, or error encountered during operation.
        
        Args:
            operation_id: Operation encountering the issue
            issue_category: Category (e.g., 'rate_limit', 'parse_error', 'network_timeout')
            description: Detailed description of the issue
            severity: 'info', 'warning', or 'error'
            affected_records: Number of records affected
            affected_items: String list/description of affected items
            resolution_attempted: Description of attempted resolution
            resolution_success: Whether resolution was successful
        """
        issue_id = str(uuid.uuid4())
        sql = """
        INSERT INTO process_issues (
            issue_id, operation_id, source_type, source_name,
            issue_category, issue_severity, issue_description,
            affected_records, affected_items, resolution_attempted, resolution_success
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        if operation_id in self._active_operations:
            op_data = self._active_operations[operation_id]
            self.db.execute(
                sql,
                (
                    issue_id,
                    operation_id,
                    op_data["source_type"],
                    op_data["source_name"],
                    issue_category,
                    severity,
                    description,
                    affected_records,
                    affected_items,
                    resolution_attempted,
                    resolution_success,
                ),
            )
            self.db.commit()
            op_data["issues"].append(
                {
                    "category": issue_category,
                    "severity": severity,
                    "description": description,
                }
            )

        log_method = getattr(logger, severity, logger.warning)
        log_method(f"Issue recorded: [{issue_category}] {description}")

    def update_record_counts(
        self,
        operation_id: str,
        attempted: int = 0,
        imported: int = 0,
        skipped: int = 0,
        failed: int = 0,
    ):
        """Update running counts of records processed during operation.
        
        Args:
            operation_id: Operation to update
            attempted: Total records attempted (+=)
            imported: Records successfully imported (+=)
            skipped: Records skipped/deduped (+=)
            failed: Records failed (+=)
        """
        if operation_id not in self._active_operations:
            return

        op = self._active_operations[operation_id]
        op["records_attempted"] += attempted
        op["records_imported"] += imported
        op["records_skipped"] += skipped
        op["records_failed"] += failed

    def get_operation_summary(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of an operation (for active operations only)."""
        if operation_id not in self._active_operations:
            return None

        op = self._active_operations[operation_id]
        duration = time.time() - op["start_time"]
        return {
            "operation_id": operation_id,
            "source": f"{op['source_type']}/{op['source_name']}",
            "duration_seconds": duration,
            "records_attempted": op["records_attempted"],
            "records_imported": op["records_imported"],
            "records_skipped": op["records_skipped"],
            "records_failed": op["records_failed"],
            "issues": len(op["issues"]),
            "success_rate": (
                (op["records_imported"] / op["records_attempted"]) * 100
                if op["records_attempted"] > 0
                else 0
            ),
        }

    def get_operation_issues(self, operation_id: str) -> list:
        """Retrieve all issues recorded for an operation from database."""
        sql = """
        SELECT issue_id, issue_category, issue_severity, issue_description,
               affected_records, resolution_success
        FROM process_issues
        WHERE operation_id = ?
        ORDER BY timestamp DESC
        """
        rows = self.db.get_all(sql, (operation_id,))
        return [dict(row) for row in rows] if rows else []
