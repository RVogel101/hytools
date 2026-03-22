"""
Tests for the metrics computation pipeline (moved from WesternArmenianLLM).
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hytools.augmentation.metrics_pipeline import (
    MetricsComputationPipeline,
    MetricComparison,
    BatchMetricsReport,
)


class TestMetricsComputationPipeline(TestCase):
    """Test metrics pipeline functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = MetricsComputationPipeline()
        self.original_text = (
            "Ես բերիմ տուն մեծ և գեղավոր։ "
            "Նա գալ է ամեն օր ժամը վեց։"
        )
        self.augmented_text = (
            "Ես բերիմ մի տուն որ շատ մեծ կար և շատ գեղավոր։ "
            "Նա գալ է ամեն մեկ օր ժամը հենց վեց։"
        )

    def test_compute_baseline(self):
        """Test baseline metric computation."""
        metrics = self.pipeline.compute_baseline(self.original_text)

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.text_id, "baseline")
        self.assertEqual(metrics.source, "original")
        self.assertGreater(metrics.text_length, 0)
        self.assertIsNotNone(metrics.lexical)
        self.assertIsNotNone(metrics.syntactic)
        self.assertIsNotNone(metrics.morphological)

    def test_compute_augmented(self):
        """Test augmented metric computation."""
        metrics = self.pipeline.compute_augmented(
            self.augmented_text,
            original_text=self.original_text,
            text_id="aug_001",
            strategy_name="paraphrase",
        )

        self.assertIsNotNone(metrics)
        self.assertIn("paraphrase", metrics.text_id)
        self.assertEqual(metrics.source, "augmented")
        self.assertGreater(metrics.text_length, 0)

    def test_compare_metrics(self):
        """Test metric comparison."""
        baseline = self.pipeline.compute_baseline(self.original_text)
        augmented = self.pipeline.compute_augmented(
            self.augmented_text,
            original_text=self.original_text,
            strategy_name="test",
        )

        comparisons = self.pipeline.compare_metrics(baseline, augmented)

        self.assertIsInstance(comparisons, dict)
        self.assertGreater(len(comparisons), 0)

        for name, comparison in comparisons.items():
            self.assertIsInstance(comparison, MetricComparison)
            self.assertIn(comparison.direction, ["increase", "decrease", "stable"])
            self.assertIsInstance(comparison.is_significant, bool)
            self.assertIsInstance(comparison.percent_change, float)

    def test_comparison_detects_significant_changes(self):
        """Test that comparison detects significant metric changes."""
        high_div_text = (
            "Ընտանիքը շատ հետաքրքիր էր։ "
            "Նրանք ունեն տուն և սիրում են գլուխ կտրել։"
        )

        baseline = self.pipeline.compute_baseline(high_div_text)

        low_div_text = "բան բան բան բան բան բան բան բան բան բան"
        augmented = self.pipeline.compute_augmented(
            low_div_text,
            original_text=high_div_text,
            strategy_name="test",
        )

        comparisons = self.pipeline.compare_metrics(baseline, augmented)

        ttr_comparison = comparisons.get("lexical_ttr")
        if ttr_comparison:
            self.assertLess(
                ttr_comparison.augmented_value,
                ttr_comparison.baseline_value,
                "Repetitive text should have lower TTR"
            )

    def test_generate_batch_report(self):
        """Test batch report generation."""
        texts = [
            "Ես տուն գտա որ շատ լավ էր։",
            "Նա գալ է վաղ է տուն հասա։",
            "Մենք բերիմ բան շատ կարևոր լինել։",
        ]

        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in texts
        ]

        report = self.pipeline.generate_batch_report(
            batch_id="test_batch_001",
            strategy_name="test",
            metric_cards=metric_cards,
        )

        self.assertIsInstance(report, BatchMetricsReport)
        self.assertEqual(report.batch_id, "test_batch_001")
        self.assertEqual(report.num_texts, 3)
        self.assertGreater(report.mean_dialect_purity, 0)
        self.assertLess(report.mean_dialect_purity, 1.01)

    def test_save_batch_report(self):
        """Test batch report saving."""
        metric_cards = [
            self.pipeline.compute_augmented("Ես տուն գտա։", strategy_name="test"),
            self.pipeline.compute_augmented("Նա գալ է։", strategy_name="test"),
        ]

        report = self.pipeline.generate_batch_report(
            batch_id="test_batch_002",
            strategy_name="test",
            metric_cards=metric_cards,
        )

        with TemporaryDirectory() as tmpdir:
            filepath = self.pipeline.save_batch_report(report, tmpdir)

            self.assertTrue(filepath.exists())

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data["batch_id"], "test_batch_002")
            self.assertEqual(data["num_texts"], 2)
            self.assertIn("metric_cards", data)

    def test_export_metrics_for_analysis(self):
        """Test CSV export for external analysis."""
        metric_cards = [
            self.pipeline.compute_augmented("Ես տուն գտա։", strategy_name="test"),
            self.pipeline.compute_augmented("Նա գալ է։", strategy_name="test"),
            self.pipeline.compute_augmented("Մենք բերիմ բան։", strategy_name="test"),
        ]

        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "metrics.csv")
            filepath = self.pipeline.export_metrics_for_analysis(metric_cards, output_file)

            self.assertTrue(filepath.exists())

            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.assertEqual(len(lines), 4)

            header = lines[0]
            self.assertIn("text_id", header)
            self.assertIn("lexical_ttr", header)
            self.assertIn("morph_em", header)

    def test_pipeline_handles_empty_batch(self):
        """Test pipeline handles empty metric card list."""
        report = self.pipeline.generate_batch_report(
            batch_id="empty_batch",
            strategy_name="test",
            metric_cards=[],
        )

        self.assertEqual(report.num_texts, 0)
        self.assertEqual(report.texts_passed_validation, 0)
        self.assertEqual(report.texts_failed_validation, 0)

    def test_metric_comparison_computation(self):
        """Test metric comparison computation specifics."""
        comparison = MetricComparison(
            metric_name="test_metric",
            baseline_value=1.0,
            augmented_value=1.5,
            change=0.5,
            percent_change=50.0,
            direction="increase",
            is_significant=True,
        )

        self.assertEqual(comparison.baseline_value, 1.0)
        self.assertEqual(comparison.augmented_value, 1.5)
        self.assertEqual(comparison.change, 0.5)
        self.assertEqual(comparison.percent_change, 50.0)
        self.assertEqual(comparison.direction, "increase")


class TestPipelineIntegration(TestCase):
    """Integration tests for pipeline with real augmentation workflow."""

    def test_pipeline_workflow(self):
        """Test complete pipeline workflow: baseline → augment → compare."""
        pipeline = MetricsComputationPipeline()

        original = "Ես բերիմ կտրակ և անվանեմ գլուխ։"
        augmented = (
            "Ես բերիմ մի կտրակ որ շատ սուր լինել կար "
            "և անվանեմ եւ ասեմ գլուխ մեծ կամ փոքր։"
        )

        baseline = pipeline.compute_baseline(original)
        self.assertIsNotNone(baseline)

        augmented_metrics = pipeline.compute_augmented(
            augmented,
            original_text=original,
            strategy_name="paraphrase",
        )
        self.assertIsNotNone(augmented_metrics)

        comparisons = pipeline.compare_metrics(baseline, augmented_metrics)
        self.assertGreater(len(comparisons), 0)

        report = pipeline.generate_batch_report(
            batch_id="workflow_test",
            strategy_name="paraphrase",
            metric_cards=[baseline, augmented_metrics],
        )
        self.assertEqual(report.num_texts, 2)
        self.assertGreater(report.mean_dialect_purity, 0)
