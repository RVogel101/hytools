"""Dialect: rule-based WA/EA/classical classification and quantitative dialect metrics."""

from .dialect_classifier import (
    DialectClassification,
    classify_text_dialect,
    classify_batch_texts,
    classify_vocab_and_sentences,
)
from .dialect_distance import (
    DistanceWeights,
    DistanceReport,
    compute_component_distance,
)
from .variant_pairs_helper import (
    build_starter_variant_pairs,
    save_variant_pairs_json,
)
from .dialect_converter import (
    to_western,
    to_eastern,
    to_classical,
    to_reform,
)
from .dialect_pair_metrics import (
    DialectPairRecord,
    DialectMetricsSummary,
    compute_dialect_pair_metrics,
    summarize_records,
)

__all__ = [
    "DialectClassification",
    "classify_text_dialect",
    "classify_batch_texts",
    "classify_vocab_and_sentences",
    "DistanceWeights",
    "DistanceReport",
    "compute_component_distance",
    "build_starter_variant_pairs",
    "save_variant_pairs_json",
    "to_western",
    "to_eastern",
    "to_classical",
    "to_reform",
    "DialectPairRecord",
    "DialectMetricsSummary",
    "compute_dialect_pair_metrics",
    "summarize_records",
]
