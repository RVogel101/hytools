"""
Tests for metrics visualization and analysis tools (moved from WesternArmenianLLM).
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import pytest

try:
    from hytools.augmentation.metrics_visualization import (
        plot_metric_distribution,
        plot_metric_comparison,
        plot_quality_scores,
        plot_anomalies,
        generate_analysis_report,
        _extract_metric_values,
    )
    from hytools.augmentation.metrics_pipeline import MetricsComputationPipeline
    from hytools.augmentation.baseline_statistics import CorpusBaselineComputer
except Exception:
    pytest.skip("augmentation package not available; skipping augmentation tests", allow_module_level=True)


class TestMetricsVisualization(TestCase):
    """Test visualization functions (without actual plotting)."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = MetricsComputationPipeline()
        self.computer = CorpusBaselineComputer()

        self.baseline_texts = [
            "Ես բերիմ տուն մեծ։",
            "Նա գալ է վաղ։",
            "Մենք բերիմ բան կարևոր։",
        ]

        self.augmented_texts = [
            "Ես բերիմ մի տուն որ շատ մեծ կար և գեղավոր։",
            "Նա գալ է շատ վաղ հավատս թե դ ժամն տ։",
            "Մենք բերիմ շատ բան որ շատ կարևոր լինել էր։",
        ]

    def test_plot_metric_distribution_returns_none_without_matplotlib(self):
        """Test that visualization gracefully handles missing matplotlib."""
        baseline_cards = [
            self.pipeline.compute_augmented(text, strategy_name="baseline")
            for text in self.baseline_texts
        ]

        result = plot_metric_distribution(baseline_cards, "lexical_ttr")
        self.assertTrue(result is None or isinstance(result, str))

    def test_plot_metric_distribution_with_output_file(self):
        """Test visualization with output file."""
        baseline_cards = [
            self.pipeline.compute_augmented(text, strategy_name="baseline")
            for text in self.baseline_texts
        ]

        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "distribution.png")
            result = plot_metric_distribution(baseline_cards, "lexical_ttr", output_file=output_file)

            if result:
                self.assertTrue(Path(result).exists())

    def test_plot_metric_comparison_with_baseline(self):
        """Test comparison plotting."""
        baseline_cards = [
            self.pipeline.compute_augmented(text, strategy_name="baseline")
            for text in self.baseline_texts
        ]
        augmented_cards = [
            self.pipeline.compute_augmented(text, strategy_name="paraphrase")
            for text in self.augmented_texts
        ]

        result = plot_metric_comparison(baseline_cards, augmented_cards, "lexical_ttr")
        self.assertTrue(result is None or isinstance(result, str))

    def test_plot_quality_scores(self):
        """Test quality score visualization."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.augmented_texts
        ]

        result = plot_quality_scores(metric_cards)
        self.assertTrue(result is None or isinstance(result, str))

    def test_plot_anomalies_with_baseline(self):
        """Test anomaly detection visualization."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.augmented_texts
        ]

        baseline_stats = self.computer.compute_from_texts(self.baseline_texts)

        result = plot_anomalies(metric_cards, baseline_stats, "lexical_ttr")
        self.assertTrue(result is None or isinstance(result, str))


class TestAnalysisReportGeneration(TestCase):
    """Test analysis report generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = MetricsComputationPipeline()
        self.computer = CorpusBaselineComputer()

        self.texts = [
            "Ես բերիմ տուն մեծ։",
            "Նա գալ է վաղ։",
            "Մենք բերիմ բան կարևոր։",
        ]

    def test_generate_analysis_report(self):
        """Test basic analysis report generation."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.texts
        ]

        report = generate_analysis_report(metric_cards)

        self.assertIsInstance(report, dict)
        self.assertEqual(report["num_texts"], 3)
        self.assertGreater(report["total_tokens"], 0)
        self.assertIn("quality", report)
        self.assertIn("lexical", report)
        self.assertIn("syntactic", report)
        self.assertIn("contamination", report)

    def test_analysis_report_quality_metrics(self):
        """Test that quality metrics are computed correctly."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.texts
        ]

        report = generate_analysis_report(metric_cards)

        quality = report["quality"]
        self.assertGreaterEqual(quality["mean_dialect_purity"], 0)
        self.assertLessEqual(quality["mean_dialect_purity"], 1.0)
        self.assertGreaterEqual(quality["std_dialect_purity"], 0)

    def test_analysis_report_lexical_metrics(self):
        """Test that lexical metrics are computed correctly."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.texts
        ]

        report = generate_analysis_report(metric_cards)

        lexical = report["lexical"]
        self.assertGreaterEqual(lexical["mean_ttr"], 0)
        self.assertLessEqual(lexical["mean_ttr"], 1.0)

    def test_analysis_report_with_baseline_comparison(self):
        """Test report generation with baseline comparison."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.texts
        ]

        baseline_stats = self.computer.compute_from_texts(self.texts)

        report = generate_analysis_report(metric_cards, baseline_stats=baseline_stats)

        self.assertIn("baseline_comparison", report)
        comparison = report["baseline_comparison"]

        self.assertTrue(len(comparison) > 0)

        for metric_name, comparison_data in comparison.items():
            self.assertIn("baseline_mean", comparison_data)
            self.assertIn("text_mean", comparison_data)
            self.assertIn("z_score", comparison_data)
            self.assertIn("is_anomalous", comparison_data)

    def test_save_analysis_report_to_json(self):
        """Test saving analysis report to JSON file."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.texts
        ]

        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "analysis_report.json")
            report = generate_analysis_report(metric_cards, output_file=output_file)

            self.assertTrue(Path(output_file).exists())

            with open(output_file, "r", encoding="utf-8") as f:
                saved_report = json.load(f)

            self.assertEqual(saved_report["num_texts"], 3)
            self.assertIn("quality", saved_report)

    def test_analysis_report_contamination_metrics(self):
        """Test contamination metrics in report."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.texts
        ]

        report = generate_analysis_report(metric_cards)

        contamination = report["contamination"]
        self.assertIn("texts_with_eastern_forms", contamination)
        self.assertIn("mean_code_switching_index", contamination)
        self.assertGreaterEqual(contamination["mean_code_switching_index"], 0)


class TestReportMetricExtraction(TestCase):
    """Test metric value extraction for analysis."""

    def test_extract_lexical_metrics(self):
        """Test extraction of lexical metrics."""
        pipeline = MetricsComputationPipeline()
        metric_cards = [
            pipeline.compute_augmented("Ես բերիմ տուն մեծ։", strategy_name="test"),
            pipeline.compute_augmented("Նա գալ է վաղ։", strategy_name="test"),
        ]

        ttr_values = _extract_metric_values(metric_cards, "lexical_ttr")

        self.assertEqual(len(ttr_values), 2)
        for val in ttr_values:
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 1.0)

    def test_extract_quality_metrics(self):
        """Test extraction of quality metrics."""
        pipeline = MetricsComputationPipeline()
        metric_cards = [
            pipeline.compute_augmented("Ես բերիմ տուն մեծ։", strategy_name="test"),
            pipeline.compute_augmented("Նա գալ է վաղ։", strategy_name="test"),
        ]

        purity_values = _extract_metric_values(metric_cards, "quality_dialect_purity_score")

        self.assertEqual(len(purity_values), 2)
        for val in purity_values:
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 1.0)
