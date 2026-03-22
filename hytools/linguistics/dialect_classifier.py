"""Compatibility module for hytools.linguistics.dialect_classifier."""

from .dialect.dialect_classifier import *

__all__ = [
    "DialectClassification",
    "classify_text_dialect",
    "classify_batch_texts",
    "classify_vocab_and_sentences",
]
