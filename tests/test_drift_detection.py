"""
Tests for drift detection and anomaly alerts (moved from WesternArmenianLLM).
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import pytest

try:
    from hytools.augmentation.drift_detection import (
        AlertReporter,
        AlertSeverity,
        DriftDetector,
        MetricAlert,
    )
    from hytools.augmentation.baseline_statistics import CorpusBaselineComputer
    from hytools.augmentation.metrics_pipeline import MetricsComputationPipeline
except Exception:
    pytest.skip("augmentation package not available; skipping augmentation tests", allow_module_level=True)


class TestDriftDetector(TestCase):
    """Test drift detection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = MetricsComputationPipeline()
        self.computer = CorpusBaselineComputer()

        self.baseline_texts = [
            "Ես բերիմ տուն մեծ և գեղավոր։",
            "Նա գալ է ամեն օր ժամը վեց։",
            "Մենք բերիմ բան շատ կարևոր։",
        ]

        self.baseline_stats = self.computer.compute_from_texts(self.baseline_texts)
        self.detector = DriftDetector(self.baseline_stats, z_score_threshold=2.0)

    def test_detector_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector)
        self.assertEqual(self.detector.z_score_threshold, 2.0)
        self.assertIsNotNone(self.detector.baseline_stats)

    def test_detect_anomalies_in_normal_batch(self):
        test_texts = [
            "Ես բերիմ տուն մեծ և գեղավոր։",
            "Նա գալ է ամեն օր ժամը վեց։",
        ]

        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in test_texts
        ]

        report = self.detector.detect_anomalies_in_batch(metric_cards, "batch_001")

        self.assertIsNotNone(report)
        self.assertEqual(report.batch_id, "batch_001")
        self.assertEqual(report.num_texts, 2)
        self.assertIsInstance(report.alerts, list)

    def test_drift_report_structure(self):
        """Test drift report data structure."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.baseline_texts[:1]
        ]

        report = self.detector.detect_anomalies_in_batch(metric_cards, "batch_struct")

        self.assertIsNotNone(report.batch_id)
        self.assertGreater(report.num_texts, 0)
        self.assertIsNotNone(report.detection_time)
        self.assertIsInstance(report.alerts, list)
        self.assertIsNotNone(report.overall_risk_level)


class TestAlertReporter(TestCase):
    """Test alert reporting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.reporter = AlertReporter()
        self.pipeline = MetricsComputationPipeline()
        self.computer = CorpusBaselineComputer()

        baseline_texts = [
            "Ես բերիմ տուն մեծ։",
            "Նա գալ է վաղ։",
        ]

        self.baseline_stats = self.computer.compute_from_texts(baseline_texts)
        self.detector = DriftDetector(self.baseline_stats)

    def test_reporter_initialization(self):
        """Test reporter initialization."""
        self.assertEqual(len(self.reporter.reports), 0)

    def test_add_report(self):
        """Test adding reports to reporter."""
        metric_cards = [
            self.pipeline.compute_augmented("Ես բերիմ տուն մեծ։", strategy_name="test")
        ]

        report = self.detector.detect_anomalies_in_batch(metric_cards, "batch_001")
        self.reporter.add_report(report)

        self.assertEqual(len(self.reporter.reports), 1)

    def test_get_summary(self):
        """Test getting summary statistics."""
        metric_cards = [
            self.pipeline.compute_augmented("Ես բերիմ տուն մեծ։", strategy_name="test")
        ]

        report = self.detector.detect_anomalies_in_batch(metric_cards, "batch_summary")
        self.reporter.add_report(report)

        summary = self.reporter.get_summary()

        self.assertIn("total_reports", summary)
        self.assertIn("total_alerts", summary)
        self.assertIn("critical_alerts", summary)
        self.assertIn("warning_alerts", summary)
        self.assertIn("info_alerts", summary)


class TestAlertSeverity(TestCase):
    """Test alert severity determination."""

    def test_severity_values(self):
        """Test severity enum values."""
        self.assertEqual(AlertSeverity.INFO.value, "info")
        self.assertEqual(AlertSeverity.WARNING.value, "warning")
        self.assertEqual(AlertSeverity.CRITICAL.value, "critical")


class TestMetricAlert(TestCase):
    """Test metric alert data structure."""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = MetricAlert(
            alert_id="test_001",
            severity=AlertSeverity.WARNING,
            metric_name="lexical_ttr",
            issue_description="TTR is out of normal range",
            affected_texts=["text_001", "text_002"],
            baseline_value=0.65,
            observed_value=0.85,
            z_score=2.1,
            threshold=2.0,
        )

        self.assertEqual(alert.alert_id, "test_001")
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(len(alert.affected_texts), 2)

    def test_alert_to_dict(self):
        """Test converting alert to dictionary."""
        alert = MetricAlert(
            alert_id="test_001",
            severity=AlertSeverity.INFO,
            metric_name="test_metric",
            issue_description="Test issue",
            affected_texts=["text_001"],
            baseline_value=1.0,
            observed_value=1.1,
            z_score=0.5,
            threshold=2.0,
        )

        alert_dict = alert.to_dict()

        self.assertIsInstance(alert_dict, dict)
        self.assertEqual(alert_dict["alert_id"], "test_001")
        self.assertEqual(alert_dict["metric_name"], "test_metric")
