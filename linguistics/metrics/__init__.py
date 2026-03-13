"""Linguistic metrics for augmentation pipeline (validation, vocabulary, text stats).

Dialect distance, clustering, pair metrics, and variant pairs moved to linguistics.dialect.
"""

from .validation import (
    validate_augmentation_output,
    generate_regeneration_prompt,
    ValidationResult,
    validate_classical_spelling,
    validate_nayiri_dictionary,
)
from .vocabulary_filter import WesternArmenianVocabularyFilter, get_vocabulary_filter
from .text_metrics import TextMetricCard, QuantitativeLinguisticsAnalyzer
from .corpus_vocabulary_builder import CorpusVocabularyBuilder

__all__ = [
    "validate_augmentation_output",
    "generate_regeneration_prompt",
    "ValidationResult",
    "validate_classical_spelling",
    "validate_nayiri_dictionary",
    "WesternArmenianVocabularyFilter",
    "get_vocabulary_filter",
    "TextMetricCard",
    "QuantitativeLinguisticsAnalyzer",
    "CorpusVocabularyBuilder",
]
