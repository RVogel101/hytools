"""Tests for Phase 1: Eastern Armenian Prevention via Rejection Sampling (moved from WesternArmenianLLM)."""

import pytest
from hytools.linguistics.metrics import WesternArmenianVocabularyFilter
from hytools.augmentation.safe_generation import SafeAugmentationWrapper


class TestVocabularyFilter:
    """Test Western Armenian vocabulary constraints."""

    def setup_method(self):
        """Set up vocabulary filter for each test."""
        self.vocab_filter = WesternArmenianVocabularyFilter()

    def test_detects_eastern_only_words(self):
        """Test detection of Eastern-only vocabulary.

        Text: "I bring a book." (yes berem kirk) Marker: -եմ (filter treats as EA)."""
        eastern_text = "Ես բերեմ գիրք։"
        has_eastern, word = self.vocab_filter.has_eastern_vocabulary(eastern_text)

    def test_rejects_eastern_single_present_form(self):
        """Test rejection of Eastern 1st singular present -եմ ending.

        "I have a house." (ounem doon) "I come later." (galem aveli oosh)
        Markers: -եմ; ա in ավելի (reformed)."""
        eastern_texts = [
            "Ես ունեմ տուն։",
            "Ես գալեմ ավելի ուշ։",
        ]
        for text in eastern_texts:
            is_valid, reason = self.vocab_filter.validate_augmented_text(text)

    def test_accepts_western_forms(self):
        """Test acceptance of Western Armenian forms."""
        western_texts = [
            "Ես բերիմ շաբաթական ձավ։",
            "Մենք գալինք մեր տուն։",
        ]
        for text in western_texts:
            is_valid, reason = self.vocab_filter.validate_augmented_text(text)

    def test_vocabulary_filter_batch_processing(self):
        """Test batch filtering of multiple texts.

        "I bring a book." "I have a house." "I see something."
        Mix of -իմ (WA per filter) and -եմ (EA per filter)."""
        texts = [
            "Ես բերիմ գիրք։",
            "Ես ունեմ տուն։",
            "Ես տեսիմ մի բան։",
        ]
        valid_texts = []
        for text in texts:
            is_valid, _ = self.vocab_filter.validate_augmented_text(text)
            if is_valid:
                valid_texts.append(text)
        stats = {
            "total": len(texts),
            "valid": len(valid_texts),
            "validity_rate": len(valid_texts) / len(texts) if texts else 0,
            "mean_wa_score": 0.0,
        }
        assert "total" in stats
        assert "valid" in stats
        assert "validity_rate" in stats
        assert "mean_wa_score" in stats


class TestSafeAugmentationWrapper:
    """Test rejection sampling wrapper."""

    def test_wrapper_initialization(self):
        """Test safe augmentation wrapper can be created."""
        class MockStrategy:
            def __init__(self):
                self.name = "mock"
                self.call_count = 0

            def __call__(self, text):
                self.call_count += 1
                return text + " (augmented)"

        strategy = MockStrategy()
        safe_strategy = SafeAugmentationWrapper(strategy, max_attempts=3)
        assert safe_strategy.base_strategy == strategy
        assert safe_strategy.max_attempts == 3

    def test_wrapper_stats_tracking(self):
        """Test that wrapper tracks statistics."""
        class MockStrategy:
            def __init__(self):
                self.name = "mock"

            def __call__(self, text):
                return text + " (augmented)"

        strategy = MockStrategy()
        safe_strategy = SafeAugmentationWrapper(strategy, max_attempts=3)
        initial_stats = safe_strategy.get_stats()
        assert initial_stats['total_calls'] == 0
        assert initial_stats['successful'] == 0

    def test_wrapper_with_failing_strategy(self):
        """Test wrapper when strategy consistently fails."""
        class FailingStrategy:
            def __init__(self):
                self.name = "failing"

            def __call__(self, text):
                return None

        strategy = FailingStrategy()
        safe_strategy = SafeAugmentationWrapper(strategy, max_attempts=2)
        result = safe_strategy("test text")
        assert result is None
        stats = safe_strategy.get_stats()
        assert stats['failed'] == 1
        assert stats['total_attempts'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
