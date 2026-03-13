"""
Drift detection and anomaly alerts for text augmentation quality monitoring.

Tracks metric changes over time to detect:
1. Individual anomalies: Single texts deviating from baseline
2. Batch drift: Systematic changes in metric means over batches
3. Quality degradation: Progressive decline in dialect purity
4. Contamination spikes: Sudden increase in Eastern Armenian forms
5. Lexical drift: Changes in vocabulary diversity patterns

Alerts are ranked by severity and can be exported for monitoring dashboards.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

from linguistics.metrics import TextMetricCard
from augmentation.baseline_statistics import CorpusBaselineStatistics


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricAlert:
    """An anomaly alert for a metric."""
    alert_id: str
    severity: AlertSeverity
    metric_name: str
    issue_description: str
    affected_texts: list[str]
    baseline_value: float
    observed_value: float
    z_score: float
    threshold: float
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DriftReport:
    """Report of metric drift detection."""
    batch_id: str
    num_texts: int
    detection_time: str
    alerts: list[MetricAlert]
    is_quality_degraded: bool
    is_contamination_spiked: bool
    is_diversity_drift: bool
    overall_risk_level: AlertSeverity
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["alerts"] = [alert.to_dict() for alert in self.alerts]
        data["severity"] = self.overall_risk_level.value
        return data


class DriftDetector:
    """Detect and alert on metric drift and anomalies."""

    def __init__(
        self,
        baseline_stats: CorpusBaselineStatistics,
        z_score_threshold: float = 2.0,
    ):
        """Initialize drift detector.
        
        Args:
            baseline_stats: Baseline statistics for comparison
            z_score_threshold: Z-score threshold for anomalies
        """
        self.baseline_stats = baseline_stats
        self.z_score_threshold = z_score_threshold
        self.alert_counter = 0

    def detect_anomalies_in_batch(
        self,
        metric_cards: list[TextMetricCard],
        batch_id: str,
    ) -> DriftReport:
        """Detect anomalies in a batch of texts.
        
        Args:
            metric_cards: Metric cards from batch
            batch_id: Batch identifier
        
        Returns:
            DriftReport with all detected issues
        """
        from datetime import datetime
        
        alerts = []
        
        # Check each metric for anomalies
        anomalies = self._detect_metric_anomalies(metric_cards)
        alerts.extend(anomalies)
        
        # Check for batch-level drift
        drift_alerts = self._detect_batch_drift(metric_cards, batch_id)
        alerts.extend(drift_alerts)
        
        # Detect contamination spikes
        contamination_alerts = self._detect_contamination_spike(metric_cards, batch_id)
        alerts.extend(contamination_alerts)
        
        # Detect diversity drift
        diversity_alerts = self._detect_diversity_drift(metric_cards, batch_id)
        alerts.extend(diversity_alerts)
        
        # Determine overall risk level
        overall_risk = self._calculate_overall_risk(alerts)
        
        # Flag specific issues
        is_quality_degraded = any(
            "dialect purity" in alert.issue_description.lower()
            and alert.severity == AlertSeverity.CRITICAL
            for alert in alerts
        )
        
        is_contamination_spiked = any(
            "contamination" in alert.issue_description.lower()
            and alert.severity == AlertSeverity.CRITICAL
            for alert in alerts
        )
        
        is_diversity_drift = any(
            "diversity" in alert.issue_description.lower()
            for alert in alerts
        )
        
        return DriftReport(
            batch_id=batch_id,
            num_texts=len(metric_cards),
            detection_time=datetime.now().isoformat(),
            alerts=alerts,
            is_quality_degraded=is_quality_degraded,
            is_contamination_spiked=is_contamination_spiked,
            is_diversity_drift=is_diversity_drift,
            overall_risk_level=overall_risk,
        )

    def _detect_metric_anomalies(
        self,
        metric_cards: list[TextMetricCard],
    ) -> list[MetricAlert]:
        """Detect individual text anomalies.
        
        Args:
            metric_cards: Metric cards to check
        
        Returns:
            List of MetricAlert objects
        """
        alerts = []
        
        # Check lexical diversity
        ttr_values = [mc.lexical.ttr for mc in metric_cards]
        ttr_alerts = self._check_metric_anomalies(
            metric_name="lexical_ttr",
            values=ttr_values,
            baseline_metric=self.baseline_stats.lexical_ttr,
            metric_cards=metric_cards,
        )
        alerts.extend(ttr_alerts)
        
        # Check dialect purity
        purity_values = [mc.quality_flags.dialect_purity_score for mc in metric_cards]
        purity_alerts = self._check_metric_anomalies(
            metric_name="quality_dialect_purity_score",
            values=purity_values,
            baseline_metric=self.baseline_stats.quality_dialect_purity,
            metric_cards=metric_cards,
        )
        alerts.extend(purity_alerts)
        
        # Check contamination index
        contam_values = [mc.contamination.code_switching_index for mc in metric_cards]
        contam_alerts = self._check_metric_anomalies(
            metric_name="contamination_code_switching_index",
            values=contam_values,
            baseline_metric=self.baseline_stats.contamination_code_switching,
            metric_cards=metric_cards,
        )
        alerts.extend(contam_alerts)
        
        return alerts

    def _check_metric_anomalies(
        self,
        metric_name: str,
        values: list[float],
        baseline_metric,
        metric_cards: list[TextMetricCard],
    ) -> list[MetricAlert]:
        """Check for anomalies in a specific metric.
        
        Args:
            metric_name: Name of metric
            values: Metric values
            baseline_metric: Baseline statistics object
            metric_cards: Associated metric cards
        
        Returns:
            List of MetricAlert objects
        """
        alerts = []
        
        for idx, value in enumerate(values):
            z_score = baseline_metric.normalize(float(value))
            if baseline_metric.is_anomaly(float(value), threshold=self.z_score_threshold):
                severity = self._get_severity_for_zscore(z_score)
                alert_id = f"anomaly_{self.alert_counter:06d}"
                self.alert_counter += 1
                alerts.append(MetricAlert(
                    alert_id=alert_id,
                    severity=severity,
                    metric_name=metric_name,
                    issue_description=f"Text {idx}: {metric_name} is {abs(z_score):.2f}σ from baseline",
                    affected_texts=[metric_cards[idx].text_id],
                    baseline_value=baseline_metric.mean,
                    observed_value=float(value),
                    z_score=float(z_score),
                    threshold=self.z_score_threshold,
                ))
        
        return alerts

    def _detect_batch_drift(
        self,
        metric_cards: list[TextMetricCard],
        batch_id: str,
    ) -> list[MetricAlert]:
        """Detect systematic drift in batch metrics.
        
        Args:
            metric_cards: Metric cards from batch
            batch_id: Batch identifier
        
        Returns:
            List of MetricAlert objects
        """
        alerts = []
        
        # Check if batch mean diverges from baseline
        batch_mean_purity = float(np.mean([mc.quality_flags.dialect_purity_score for mc in metric_cards]))
        batch_mean_ttr = float(np.mean([mc.lexical.ttr for mc in metric_cards]))
        purity_stats = self.baseline_stats.quality_dialect_purity
        ttr_stats = self.baseline_stats.lexical_ttr
        if purity_stats is None or ttr_stats is None:
            return alerts
        # Check dialect purity
        z_purity = purity_stats.normalize(batch_mean_purity)
        if abs(z_purity) > self.z_score_threshold:
            severity = self._get_severity_for_zscore(z_purity)
            
            alert_id = f"drift_{self.alert_counter:06d}"
            self.alert_counter += 1
            
            alerts.append(MetricAlert(
                alert_id=alert_id,
                severity=severity,
                metric_name="batch_dialect_purity_drift",
                issue_description=f"Batch {batch_id}: Dialect purity mean is {abs(z_purity):.2f}σ from baseline",
                affected_texts=[mc.text_id for mc in metric_cards],
                baseline_value=purity_stats.mean,
                observed_value=float(batch_mean_purity),
                z_score=float(z_purity),
                threshold=self.z_score_threshold,
            ))
        
        # Check TTR
        z_ttr = ttr_stats.normalize(batch_mean_ttr)
        if abs(z_ttr) > self.z_score_threshold:
            severity = self._get_severity_for_zscore(z_ttr)
            
            alert_id = f"drift_{self.alert_counter:06d}"
            self.alert_counter += 1
            
            alerts.append(MetricAlert(
                alert_id=alert_id,
                severity=severity,
                metric_name="batch_ttr_drift",
                issue_description=f"Batch {batch_id}: TTR mean is {abs(z_ttr):.2f}σ from baseline",
                affected_texts=[mc.text_id for mc in metric_cards],
                baseline_value=ttr_stats.mean,
                observed_value=float(batch_mean_ttr),
                z_score=float(z_ttr),
                threshold=self.z_score_threshold,
            ))
        
        return alerts

    def _detect_contamination_spike(
        self,
        metric_cards: list[TextMetricCard],
        batch_id: str,
    ) -> list[MetricAlert]:
        """Detect spikes in Eastern Armenian contamination.
        
        Args:
            metric_cards: Metric cards from batch
            batch_id: Batch identifier
        
        Returns:
            List of MetricAlert objects
        """
        alerts = []
        
        # Find texts with any contamination
        contaminated_texts = [
            mc for mc in metric_cards
            if mc.contamination.code_switching_index > 0
        ]
        
        if len(contaminated_texts) > len(metric_cards) * 0.1:  # More than 10% contaminated
            alert_id = f"spike_{self.alert_counter:06d}"
            self.alert_counter += 1
            
            contamination_rate = len(contaminated_texts) / len(metric_cards)
            cc_stats = self.baseline_stats.contamination_code_switching
            baseline_mean = cc_stats.mean if cc_stats is not None else 0.0
            alerts.append(MetricAlert(
                alert_id=alert_id,
                severity=AlertSeverity.CRITICAL,
                metric_name="contamination_spike",
                issue_description=f"Batch {batch_id}: {contamination_rate*100:.1f}% of texts contain Eastern Armenian forms",
                affected_texts=[mc.text_id for mc in contaminated_texts],
                baseline_value=baseline_mean,
                observed_value=float(contamination_rate),
                z_score=2.5,
                threshold=self.z_score_threshold,
            ))
        
        return alerts

    def _detect_diversity_drift(
        self,
        metric_cards: list[TextMetricCard],
        batch_id: str,
    ) -> list[MetricAlert]:
        """Detect changes in vocabulary diversity patterns.
        
        Args:
            metric_cards: Metric cards from batch
            batch_id: Batch identifier
        
        Returns:
            List of MetricAlert objects
        """
        alerts = []
        
        sttr_values = [mc.lexical.sttr for mc in metric_cards]
        batch_mean_sttr = float(np.mean(sttr_values))
        sttr_stats = self.baseline_stats.lexical_sttr
        if sttr_stats is None:
            return alerts
        z_sttr = sttr_stats.normalize(batch_mean_sttr)
        
        if abs(z_sttr) > self.z_score_threshold:
            severity = self._get_severity_for_zscore(z_sttr)
            
            alert_id = f"drift_{self.alert_counter:06d}"
            self.alert_counter += 1
            
            alerts.append(MetricAlert(
                alert_id=alert_id,
                severity=severity,
                metric_name="diversity_drift",
                issue_description=f"Batch {batch_id}: Standardized TTR (STTR) shows {abs(z_sttr):.2f}σ drift",
                affected_texts=[mc.text_id for mc in metric_cards],
                baseline_value=sttr_stats.mean,
                observed_value=float(batch_mean_sttr),
                z_score=float(z_sttr),
                threshold=self.z_score_threshold,
            ))
        
        return alerts

    def _calculate_overall_risk(self, alerts: list[MetricAlert]) -> AlertSeverity:
        """Calculate overall risk level from alerts.
        
        Args:
            alerts: List of alerts
        
        Returns:
            Overall AlertSeverity
        """
        if not alerts:
            return AlertSeverity.INFO
        
        if any(alert.severity == AlertSeverity.CRITICAL for alert in alerts):
            return AlertSeverity.CRITICAL
        
        if any(alert.severity == AlertSeverity.WARNING for alert in alerts):
            return AlertSeverity.WARNING
        
        return AlertSeverity.INFO

    def _get_severity_for_zscore(self, z_score: float) -> AlertSeverity:
        """Determine severity from z-score magnitude.
        
        Args:
            z_score: Z-score value
        
        Returns:
            AlertSeverity level
        """
        abs_z = abs(z_score)
        
        if abs_z > 3.0:
            return AlertSeverity.CRITICAL
        elif abs_z > 2.5:
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO


class AlertReporter:
    """Report and export alerts."""

    def __init__(self):
        """Initialize reporter."""
        self.reports = []

    def add_report(self, report: DriftReport):
        """Add drift report.
        
        Args:
            report: DriftReport to add
        """
        self.reports.append(report)

    def get_critical_alerts(self) -> list[MetricAlert]:
        """Get all critical alerts.
        
        Returns:
            List of critical MetricAlert objects
        """
        critical = []
        for report in self.reports:
            critical.extend([
                alert for alert in report.alerts
                if alert.severity == AlertSeverity.CRITICAL
            ])
        return critical

    def get_summary(self) -> dict:
        """Get summary of all alerts.
        
        Returns:
            Summary statistics
        """
        all_alerts = []
        for report in self.reports:
            all_alerts.extend(report.alerts)
        
        return {
            "total_reports": len(self.reports),
            "total_alerts": len(all_alerts),
            "critical_alerts": len([a for a in all_alerts if a.severity == AlertSeverity.CRITICAL]),
            "warning_alerts": len([a for a in all_alerts if a.severity == AlertSeverity.WARNING]),
            "info_alerts": len([a for a in all_alerts if a.severity == AlertSeverity.INFO]),
        }

    def export_alerts_json(self, output_file: str) -> Path:
        """Export all alerts to JSON file.
        
        Args:
            output_file: Output file path
        
        Returns:
            Path to exported file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "summary": self.get_summary(),
            "reports": [report.to_dict() for report in self.reports],
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return output_path

    def print_summary(self):
        """Print alert summary to console."""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("ALERT SUMMARY")
        print("="*60)
        print(f"Total Reports: {summary['total_reports']}")
        print(f"Total Alerts: {summary['total_alerts']}")
        print(f"  🔴 Critical: {summary['critical_alerts']}")
        print(f"  🟡 Warning:  {summary['warning_alerts']}")
        print(f"  🔵 Info:     {summary['info_alerts']}")
        print("="*60)
        
        # Print critical alerts
        critical = self.get_critical_alerts()
        if critical:
            print("\nCRITICAL ALERTS:")
            for alert in critical:
                print(f"  [{alert.alert_id}] {alert.metric_name}")
                print(f"    → {alert.issue_description}")
                print(f"    → Baseline: {alert.baseline_value:.4f}, Observed: {alert.observed_value:.4f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m augmentation.drift_detection",
        description="Detect metric drift for Western and Eastern Armenian texts.",
    )
    parser.add_argument("--baseline-wa", default="cache/wa_metric_baseline_stats.json", help="WA baseline stats JSON")
    parser.add_argument("--baseline-ea", default="cache/ea_metric_baseline_stats.json", help="EA baseline stats JSON")
    parser.add_argument("--metric-cards-dir", default="cache/metric_cards", help="Dir with metric card JSONs")
    parser.add_argument("--output", default="cache/drift_report.json", help="Output report path")
    parser.add_argument("--z-threshold", type=float, default=2.0, help="Z-score threshold for anomalies")
    args = parser.parse_args()

    from augmentation.baseline_statistics import CorpusBaselineComputer

    computer = CorpusBaselineComputer()
    wa_baseline = computer.load_statistics(args.baseline_wa)
    ea_baseline = computer.load_statistics(args.baseline_ea)

    if wa_baseline is None and ea_baseline is None:
        raise SystemExit(
            "No baseline stats found. Run: python -m augmentation.baseline_statistics --mongodb"
        )

    detectors = {}
    if wa_baseline:
        detectors["wa"] = DriftDetector(wa_baseline, z_score_threshold=args.z_threshold)
        print("✓ WA drift detector ready")
    if ea_baseline:
        detectors["ea"] = DriftDetector(ea_baseline, z_score_threshold=args.z_threshold)
        print("✓ EA drift detector ready")

    # Load metric cards from dir and run detection
    cards_dir = Path(args.metric_cards_dir)
    if cards_dir.exists():
        # TODO: Load TextMetricCards from JSON, split by dialect, run detect_anomalies_in_batch
        print(f"Metric cards dir: {cards_dir} (batch detection: integrate with metrics_pipeline)")
    else:
        print("No metric cards dir. Run metrics_pipeline to generate cards, then re-run drift_detection.")
