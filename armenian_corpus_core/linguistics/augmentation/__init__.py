"""Augmentation and dialect analysis for Armenian text.

Provides:
- Dialect distance, clustering, and pair metrics
- Text augmentation strategies (paraphrase, word dropout, shuffle, deletion)
- Vocabulary filtering and corpus vocabulary building
- Text metrics, baseline statistics, drift detection
- Validation and safe generation wrappers
"""

from .validation import (
    validate_augmentation_output,
    generate_regeneration_prompt,
    ValidationResult,
    validate_classical_spelling,
    validate_nayiri_dictionary,
)
from .vocabulary_filter import WesternArmenianVocabularyFilter, get_vocabulary_filter
from .variant_pairs_helper import build_starter_variant_pairs, save_variant_pairs_json
from .text_metrics import TextMetricCard, QuantitativeLinguisticsAnalyzer

__all__ = [
    "validate_augmentation_output",
    "generate_regeneration_prompt",
    "ValidationResult",
    "validate_classical_spelling",
    "validate_nayiri_dictionary",
    "WesternArmenianVocabularyFilter",
    "get_vocabulary_filter",
    "build_starter_variant_pairs",
    "save_variant_pairs_json",
    "TextMetricCard",
    "QuantitativeLinguisticsAnalyzer",
]
