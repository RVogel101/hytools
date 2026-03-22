"""
Tests for corpus baseline statistics computation (moved from WesternArmenianLLM).
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hytools.augmentation.baseline_statistics import (
    CorpusBaselineComputer,
    CorpusBaselineStatistics,
    MetricStatistics,
)
from hytools.augmentation.metrics_pipeline import MetricsComputationPipeline


class TestMetricStatistics(TestCase):
    """Test MetricStatistics functionality."""

    def test_metric_statistics_creation(self):
        """Test creating metric statistics."""
        stats = MetricStatistics(
            metric_name="test_metric",
            count=100,
            mean=0.5,
            std_dev=0.1,
            min_value=0.2,
            max_value=0.8,
            median=0.5,
            p25=0.4,
            p75=0.6,
        )

        self.assertEqual(stats.metric_name, "test_metric")
        self.assertEqual(stats.count, 100)
        self.assertEqual(stats.mean, 0.5)

    def test_is_anomaly_detection(self):
        """Test anomaly detection for outlier values."""
        stats = MetricStatistics(
            metric_name="test",
            count=100,
            mean=1.0,
            std_dev=0.1,
            min_value=0.5,
            max_value=1.5,
            median=1.0,
            p25=0.95,
            p75=1.05,
        )

        self.assertFalse(stats.is_anomaly(1.0))
        self.assertFalse(stats.is_anomaly(1.1))
        self.assertFalse(stats.is_anomaly(1.19))
        self.assertTrue(stats.is_anomaly(1.21))
        self.assertTrue(stats.is_anomaly(0.79))

    def test_normalize_to_zscore(self):
        """Test normalization to z-score."""
        stats = MetricStatistics(
            metric_name="test",
            count=100,
            mean=10.0,
            std_dev=2.0,
            min_value=5.0,
            max_value=15.0,
            median=10.0,
            p25=9.0,
            p75=11.0,
        )

        self.assertAlmostEqual(stats.normalize(10.0), 0.0)
        self.assertAlmostEqual(stats.normalize(12.0), 1.0)
        self.assertAlmostEqual(stats.normalize(8.0), -1.0)

    def test_percentile_rank(self):
        """Test percentile rank estimation."""
        stats = MetricStatistics(
            metric_name="test",
            count=100,
            mean=50.0,
            std_dev=10.0,
            min_value=0.0,
            max_value=100.0,
            median=50.0,
            p25=42.5,
            p75=57.5,
        )

        self.assertAlmostEqual(stats.percentile_rank(0.0), 0.0, places=1)
        self.assertAlmostEqual(stats.percentile_rank(100.0), 100.0, places=1)
        self.assertAlmostEqual(stats.percentile_rank(50.0), 50.0, places=1)


class TestCorpusBaselineComputer(TestCase):
    """Test corpus baseline statistics computation."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = MetricsComputationPipeline()
        self.computer = CorpusBaselineComputer()

        self.sample_texts = [
            "Ես բերիմ տուն մեծ։",
            "Նա գալ է վաղ։",
            "Մենք բերիմ բան կարևոր։",
            "Նրանք գերել են շատ։",
            "Դուք տեսել եք լավ տեղ։",
        ]

    def test_compute_from_texts(self):
        """Test computing baseline from raw texts."""
        stats = self.computer.compute_from_texts(self.sample_texts)

        self.assertIsInstance(stats, CorpusBaselineStatistics)
        self.assertEqual(stats.num_texts, len(self.sample_texts))
        self.assertGreater(stats.total_tokens, 0)
        self.assertIsNotNone(stats.lexical_ttr)

    def test_baseline_statistics_valid_ranges(self):
        """Test that baseline statistics are in valid ranges."""
        stats = self.computer.compute_from_texts(self.sample_texts)
        ttr = stats.lexical_ttr
        qdp = stats.quality_dialect_purity
        assert ttr is not None
        assert qdp is not None

        self.assertGreaterEqual(ttr.mean, 0)
        self.assertLessEqual(ttr.mean, 1.0)
        self.assertGreaterEqual(ttr.std_dev, 0)
        self.assertLessEqual(ttr.min_value, ttr.max_value)
        self.assertGreaterEqual(qdp.mean, 0)
        self.assertLessEqual(qdp.mean, 1.01)

    def test_compute_from_metric_cards(self):
        """Test computing baseline from existing metric cards."""
        metric_cards = [
            self.pipeline.compute_augmented(text, strategy_name="test")
            for text in self.sample_texts
        ]

        stats = self.computer.compute_from_metric_cards(metric_cards)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.num_texts, len(metric_cards))
        self.assertGreater(stats.total_tokens, 0)

    def test_save_and_load_statistics(self):
        """Test saving and loading statistics JSON."""
        stats = self.computer.compute_from_texts(self.sample_texts)

        with TemporaryDirectory() as tmpdir:
            output_file = str(Path(tmpdir) / "baseline_stats.json")

            filepath = self.computer.save_statistics(stats, output_file)
            self.assertTrue(filepath.exists())

            loaded_stats = self.computer.load_statistics(output_file)
            self.assertIsNotNone(loaded_stats)
            if loaded_stats is not None:
                self.assertEqual(loaded_stats.num_texts, stats.num_texts)
                self.assertEqual(loaded_stats.total_tokens, stats.total_tokens)

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("compute_date", data)
            self.assertIn("num_texts", data)
            self.assertIn("lexical_ttr", data)
            self.assertIn("quality_dialect_purity", data)

    def test_load_nonexistent_file_returns_none(self):
        """Test loading from non-existent file returns None."""
        stats = self.computer.load_statistics("/nonexistent/path/stats.json")
        self.assertIsNone(stats)

    def test_all_metrics_computed(self):
        """Test that all expected metrics are computed."""
        stats = self.computer.compute_from_texts(self.sample_texts)

        expected_metrics = [
            "lexical_ttr",
            "lexical_sttr",
            "lexical_yule_k",
            "syntactic_asl",
            "syntactic_clauses_per_sent",
            "syntactic_flesch_kincaid",
            "morph_em_freq",
            "morph_im_freq",
            "contamination_code_switching",
            "quality_dialect_purity",
        ]

        for metric in expected_metrics:
            metric_stats = getattr(stats, metric, None)
            self.assertIsNotNone(metric_stats, f"Missing metric: {metric}")
            if metric_stats is not None:
                self.assertGreater(metric_stats.count, 0, f"No data for metric: {metric}")

    def test_percentile_statistics(self):
        """Test that percentile statistics are computed correctly."""
        stats = self.computer.compute_from_texts(self.sample_texts)
        ttr_stats = stats.lexical_ttr
        assert ttr_stats is not None

        self.assertLessEqual(ttr_stats.min_value, ttr_stats.p25)
        self.assertLessEqual(ttr_stats.p25, ttr_stats.median)
        self.assertLessEqual(ttr_stats.median, ttr_stats.p75)
        self.assertLessEqual(ttr_stats.p75, ttr_stats.max_value)


class TestAnomalyDetection(TestCase):
    """Test anomaly detection using baseline statistics."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = MetricsComputationPipeline()
        self.computer = CorpusBaselineComputer()

        self.baseline_texts = [
            "Ես բերիմ տուն մեծ և գեղավոր։",
            "Նա գալ է ամեն օր ժամը վեց։",
            "Մենք բերիմ բան շատ կարևոր։",
        ]

    def test_detect_anomalous_text(self):
        """Test detection of anomalous text vs baseline."""
        baseline_stats = self.computer.compute_from_texts(self.baseline_texts)

        anomalous_text = "ա բ գ դ ե զ է ը թ ժ ի լ խ ծ կ հ ձ ղ ճ մ յ ն շ ո չ պ ջ ռ ս վ տ ր ց ւ փ ք"

        anomalous_metrics = self.pipeline.compute_augmented(
            anomalous_text,
            strategy_name="anomaly_test",
        )

        lexical_ttr = baseline_stats.lexical_ttr
        if lexical_ttr is None:
            self.skipTest("lexical_ttr not computed")
        ttr_is_anomalous = lexical_ttr.is_anomaly(
            anomalous_metrics.lexical.ttr,
            threshold=1.0,
        )

        self.assertTrue(ttr_is_anomalous or anomalous_metrics.lexical.ttr > 0.9)

    def test_zscore_normalization(self):
        """Test z-score normalization of metrics."""
        baseline_stats = self.computer.compute_from_texts(self.baseline_texts)

        test_text = "Ես բերիմ տուն մեծ։"
        test_metrics = self.pipeline.compute_augmented(
            test_text,
            strategy_name="test",
        )

        lexical_ttr = baseline_stats.lexical_ttr
        assert lexical_ttr is not None
        z_score = lexical_ttr.normalize(test_metrics.lexical.ttr)

        self.assertLess(abs(z_score), 10, "Z-score unreasonably large")
