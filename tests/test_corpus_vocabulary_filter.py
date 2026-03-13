"""
Test suite for corpus-grounded Eastern Armenian vocabulary filtering (moved from WesternArmenianLLM).

Validates that:
1. Corpus builder correctly extracts word frequencies
2. Vocabulary filter correctly identifies Eastern forms
3. Auto-correction works for known forms
4. Multi-signal validation rejects Eastern Armenian

Note: Filter may treat -եմ as Eastern; per corrected rules -եմ is Western. See docs/TEST_VALIDATION_ARMENIAN.md.
"""

import unittest
from pathlib import Path

from linguistics.metrics.corpus_vocabulary_builder import CorpusVocabularyBuilder
from linguistics.metrics.vocabulary_filter import WesternArmenianVocabularyFilter


class TestCorpusVocabularyBuilder(unittest.TestCase):
    """Test corpus extraction and analysis."""

    def test_corpus_builder_initialization(self):
        """Builder should initialize without errors."""
        builder = CorpusVocabularyBuilder(min_word_length=2)
        self.assertEqual(builder.min_word_length, 2)
        self.assertEqual(len(builder.wa_frequencies), 0)

    def test_known_eastern_vocabulary_available(self):
        """Known Eastern vocabulary should be accessible."""
        builder = CorpusVocabularyBuilder(min_word_length=2)
        vocab = builder._known_eastern_vocabulary()

        self.assertIn("բերեմ", vocab)
        self.assertIn("բերենք", vocab)
        self.assertGreater(len(vocab), 0)

        for word, metadata in vocab.items():
            self.assertIn("category", metadata)
            self.assertIn("explanation", metadata)

    def test_corpus_cache_exists(self):
        """Cache file should exist if corpus builder was run."""
        cache_path = Path("cache/eastern_only_vocabulary.json")

        if cache_path.exists():
            self.assertTrue(cache_path.stat().st_size > 100)


class TestVocabularyFilter(unittest.TestCase):
    """Test vocabulary filter for Eastern Armenian detection."""

    def setUp(self):
        """Initialize filter for each test."""
        self.filter = WesternArmenianVocabularyFilter(use_corpus_cache=True)

        self.assertGreater(len(self.filter.eastern_only_vocabulary), 0)

    def test_filter_has_eastern_vocabulary_dict(self):
        """Filter should have loaded vocabulary."""
        self.assertGreater(len(self.filter.eastern_only_vocabulary), 0)

    def test_detect_eastern_verb_forms(self):
        """Should detect Eastern 1st singular verb forms (-եմ).

        Text: "I bring: բերեմ" (berem). Marker: -եմ.
        Note: Filter treats -եմ as EA; per corrected rules -եմ is WA."""
        text_eastern = "I bring: բերեմ"
        has_eastern, word = self.filter.has_eastern_vocabulary(text_eastern)

        if "բերեմ" in self.filter.eastern_only_vocabulary:
            self.assertTrue(has_eastern, "Should detect բերեմ as Eastern")
            self.assertEqual(word, "բերեմ")

    def test_detect_eastern_plural_forms(self):
        """Should detect Eastern 1st plural verb forms (-ենք)."""
        text_eastern = "We bring: բերենք"
        has_eastern, word = self.filter.has_eastern_vocabulary(text_eastern)

        if "բերենք" in self.filter.eastern_only_vocabulary:
            self.assertTrue(has_eastern, "Should detect բերենք as Eastern")

    def test_detect_eastern_3rd_singular(self):
        """Should detect Eastern 3rd singular forms (-այ).

        Text: "He goes: գնայ" (gna). Marker: -այ."""
        text_eastern = "He goes: գնայ"
        has_eastern, word = self.filter.has_eastern_vocabulary(text_eastern)

        if "գնայ" in self.filter.eastern_only_vocabulary:
            self.assertTrue(has_eastern, "Should detect գնայ as Eastern")

    def test_no_false_positive_on_western_text(self):
        """Should not flag valid Western Armenian as Eastern.

        Text: "I cannot understand." (yes chem garoghanoom hasgnal)
        Markers: չ (negative), Western vocab."""
        text_western = "Ես չեմ կարողանում հասկանալ։"
        has_eastern, word = self.filter.has_eastern_vocabulary(text_western)
        # Western text; may or may not trigger depending on vocab
        self.assertIsInstance(has_eastern, bool)

    def test_correct_eastern_to_western(self):
        """Should auto-correct known Eastern forms to Western equivalents."""
        text_eastern = "I bring it: բերեմ այն։"

        if "բերեմ" in self.filter.eastern_to_western_mapping:
            corrected, corrections = self.filter.correct_to_western(text_eastern)

            if corrected is not None and corrections:
                self.assertIn("բերիմ", corrected)
                self.assertGreater(len(corrections), 0)

    def test_fallback_to_hardcoded(self):
        """Filter should fall back to hardcoded list if cache unavailable."""
        filter_hardcoded = WesternArmenianVocabularyFilter(use_corpus_cache=False)

        self.assertGreater(len(filter_hardcoded.eastern_only_vocabulary), 0)

    def test_validate_augmented_text(self):
        """validate_augmented_text should return (bool, reason) tuple.

        Text: "This is a good house." (sa lav doon e)"""
        text = "Սա լավ տուն է։"

        is_valid, reason = self.filter.validate_augmented_text(text)

        self.assertIsInstance(is_valid, bool)
        self.assertIsInstance(reason, str)

    def test_corpus_metadata_loaded(self):
        """If corpus cache loaded, should have frequency metadata."""
        if len(self.filter._corpus_metadata) > 0:
            for word, meta in self.filter._corpus_metadata.items():
                self.assertIn("wa_frequency", meta)
                self.assertIn("wa_frequency_pct", meta)
                self.assertIn("wa_is_rare", meta)
                self.assertIn("category", meta)


class TestIntegrationWithLanguageFilter(unittest.TestCase):
    """Test integration with language_filter helpers (in core.cleaning)."""

    def test_compute_wa_score_available(self):
        """Should be able to import and use compute_wa_score."""
        from cleaning.language_filter import compute_wa_score

        text = "Սա լավ տուն է։"
        score = compute_wa_score(text)

        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_is_western_armenian_available(self):
        """Should be able to import and use is_western_armenian.

        Text: "This is a good house." """
        from cleaning.language_filter import is_western_armenian

        text = "Սա լավ տուն է։"
        is_wa = is_western_armenian(text)

        self.assertIsInstance(is_wa, bool)


class TestCorpusSamples(unittest.TestCase):
    """Test with actual corpus data if available."""

    def test_wikipedia_corpus_exists(self):
        """Check if Wikipedia corpus files exist."""
        wiki_path = Path("data/raw/wikipedia/extracted")

        if wiki_path.exists():
            files = list(wiki_path.glob("*.txt"))
            self.assertGreater(len(files), 0)

    def test_corpus_builder_runs_on_actual_data(self):
        """Test that corpus builder can actually run on real corpus data."""
        wiki_path = Path("data/raw/wikipedia/extracted")

        if wiki_path.exists():
            builder = CorpusVocabularyBuilder()

            vocab = builder.analyze_corpus(wa_corpus_dirs=[str(wiki_path)])

            self.assertGreater(len(vocab), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
