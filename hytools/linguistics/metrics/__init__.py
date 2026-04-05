"""Linguistic metrics for augmentation pipeline (validation, vocabulary, text stats).

Dialect distance, clustering, pair metrics, and variant pairs moved to linguistics.dialect.
"""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "validate_augmentation_output": ("validation", "validate_augmentation_output"),
    "generate_regeneration_prompt": ("validation", "generate_regeneration_prompt"),
    "ValidationResult": ("validation", "ValidationResult"),
    "validate_classical_spelling": ("validation", "validate_classical_spelling"),
    "validate_nayiri_dictionary": ("validation", "validate_nayiri_dictionary"),
    "WesternArmenianVocabularyFilter": ("vocabulary_filter", "WesternArmenianVocabularyFilter"),
    "get_vocabulary_filter": ("vocabulary_filter", "get_vocabulary_filter"),
    "TextMetricCard": ("text_metrics", "TextMetricCard"),
    "QuantitativeLinguisticsAnalyzer": ("text_metrics", "QuantitativeLinguisticsAnalyzer"),
    "CorpusVocabularyBuilder": ("corpus_vocabulary_builder", "CorpusVocabularyBuilder"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
