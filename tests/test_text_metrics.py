"""
Tests for quantitative linguistic metrics computation (moved from WesternArmenianLLM).

Validates that all metrics compute correctly on sample texts.
See docs/TEST_VALIDATION_ARMENIAN.md for translations, transliterations, and markers.
"""

import unittest
from pathlib import Path

from hytools.linguistics.metrics.text_metrics import QuantitativeLinguisticsAnalyzer


class TestQuantitativeLinguisticsMetrics(unittest.TestCase):
    """Test metric computation on sample texts."""

    def setUp(self):
        """Initialize analyzer for each test."""
        self.analyzer = QuantitativeLinguisticsAnalyzer()

    def test_analyzer_initialization(self):
        """Analyzer should initialize without errors."""
        self.assertIsNotNone(self.analyzer)
        self.assertIsNotNone(self.analyzer.wa_baseline_frequencies)

    def test_lexical_metrics_computation(self):
        """Lexical metrics should compute correctly.

        Text: "The house is big. The house is beautiful. We love the house."
        Neutral dialect (Eastern-style -ում, -ենք)."""
        text = "Տունը մեծ է։ Տունը գեղավոր է։ Մենք տունը սիրում ենք։"

        metrics = self.analyzer.analyze_text(text, text_id="test_001")

        self.assertGreater(metrics.lexical.total_words, 0)
        self.assertGreater(metrics.lexical.unique_words, 0)
        self.assertLessEqual(metrics.lexical.unique_words, metrics.lexical.total_words)
        self.assertGreaterEqual(metrics.lexical.unique_word_rate, 0.0)
        self.assertLessEqual(metrics.lexical.unique_word_rate, 1.0)
        self.assertGreaterEqual(metrics.lexical.ttr, 0.0)
        self.assertLessEqual(metrics.lexical.ttr, 1.0)
        self.assertGreaterEqual(metrics.lexical.sttr, 0.0)
        self.assertLessEqual(metrics.lexical.sttr, 1.0)

    def test_syntactic_metrics_computation(self):
        """Syntactic metrics should compute correctly."""
        text = "Տունը մեծ է։ Այն գեղավոր է։ Մենք այստեղ ապրում ենք և շատ բազմում ենք այս տեղ։"

        metrics = self.analyzer.analyze_text(text, text_id="test_002")

        self.assertGreater(metrics.syntactic.avg_sentence_length, 0)
        self.assertGreaterEqual(metrics.syntactic.clauses_per_sentence, 0)
        self.assertGreater(metrics.syntactic.flesch_kincaid_grade, 0)

    def test_morphological_suffix_tracking(self):
        """Morphological suffix metrics: -եմ = WA, -ում = EA.

        Western: "I bring and write that house." Markers: -եմ (բերեմ, գրեմ).
        Eastern: "I am bringing and writing that house." Markers: -ում (բերում, գրում)."""
        text_western = "Ես բերեմ ու գրեմ այն տուն։"
        metrics_wa = self.analyzer.analyze_text(text_western, text_id="test_wa")

        text_eastern = "Ես բերում եմ ու գրում եմ այն տուն։"
        metrics_ea = self.analyzer.analyze_text(text_eastern, text_id="test_ea")

        self.assertGreaterEqual(
            metrics_wa.morphological.suffix_em_count,
            1,
            "Western uses -եմ (e.g. բերեմ)",
        )
        self.assertGreater(
            metrics_ea.morphological.suffix_um_count,
            metrics_wa.morphological.suffix_um_count,
            "-ում is Eastern imperfective; Western does not use -ում",
        )

    def test_orthographic_metrics_computation(self):
        """Orthographic metrics should detect classical vs reformed patterns."""
        text = "Մեր տունը մեծ է։ Ինքը շատ գեղավոր տեղ է։"

        metrics = self.analyzer.analyze_text(text, text_id="test_003")

        self.assertGreaterEqual(metrics.orthographic.classical_markers_count, 0)
        self.assertGreaterEqual(metrics.orthographic.reformed_markers_count, 0)
        self.assertGreaterEqual(metrics.orthographic.classical_to_reformed_ratio, 0)

    def test_quality_flags_generation(self):
        """Quality flags should be generated and within valid ranges.

        Text: "The house is big and beautiful." """
        text = "Տունը մեծ և գեղավոր է։"

        metrics = self.analyzer.analyze_text(text, text_id="test_quality")

        self.assertGreaterEqual(metrics.quality_flags.dialect_purity_score, 0.0)
        self.assertLessEqual(metrics.quality_flags.dialect_purity_score, 1.0)
        self.assertIsInstance(metrics.quality_flags.potential_issues, list)

    def test_metric_card_json_serialization(self):
        """Metric cards should serialize to valid JSON.

        Text: "The house is big." """
        text = "Տունը մեծ է։"

        metrics = self.analyzer.analyze_text(text, text_id="test_json")
        json_str = self.analyzer.to_json(metrics)

        self.assertIsInstance(json_str, str)
        self.assertGreater(len(json_str), 100)

        import json
        json.loads(json_str)


class TestMetricInterpretation(unittest.TestCase):
    """Test metric value interpretation."""

    def setUp(self):
        self.analyzer = QuantitativeLinguisticsAnalyzer()

    def test_high_ttr_indicates_diversity(self):
        """High TTR should indicate diverse vocabulary.

        Text: "The house is big, beautiful, old, where special, enchanting high architecture lives." """
        diverse_text = (
            "Տունը մեծ, գեղավոր, հին, որտեղ ապրում է հատուկ, հմայական, բարձր արխիտեկտուր։"
        )
        metrics = self.analyzer.analyze_text(diverse_text, text_id="diverse")

        self.assertGreater(metrics.lexical.ttr, 0.6)

    def test_debug_marker_helpers(self):
        """Debug helpers should locate specific suffix/orthographic triggers."""
        # Contains a classical marker (եա) and reformed endings (word-final ա, թյուն)
        text = "մեա տունան թյուն"
        words = text.split()

        suffix_debug = self.analyzer.debug_morphological_suffixes(words)
        self.assertIn("suffix_an_words", suffix_debug)
        self.assertIn("տունան", suffix_debug["suffix_an_words"])  # word ending with 'ան'
        self.assertIn("suffix_ian_words", suffix_debug)

        orth_debug = self.analyzer.debug_orthographic_markers(text)
        self.assertIn("classical", orth_debug)
        self.assertIn("reformed", orth_debug)
        # Ensure classical markers capture 'եա'
        self.assertTrue(any("եա" in ''.join(vals) for vals in orth_debug["classical"].values()))
        # Ensure reformed markers capture word-final 'ա' and 'թյուն'
        self.assertTrue(any("ա" in ''.join(vals) for vals in orth_debug["reformed"].values()))
        self.assertTrue(any("թյուն" in ''.join(vals) for vals in orth_debug["reformed"].values()))

    def test_low_ttr_indicates_repetition(self):
        """Low TTR should indicate repetitive vocabulary.

        Text: "The house is a house." (repeated)"""
        repetitive_text = "Տունը տուն է։ Տունը տուն է։ Տունը տուն է։"
        metrics = self.analyzer.analyze_text(repetitive_text, text_id="repetitive")

        self.assertLess(metrics.lexical.ttr, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
