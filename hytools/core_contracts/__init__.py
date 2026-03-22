"""Core domain contracts for migration-safe integration."""

from .hashing import normalize_text_for_hash, sha256_normalized
from .types import DialectTag, DocumentRecord, LexiconEntry, PhoneticResult

__all__ = [
    "DialectTag",
    "DocumentRecord",
    "LexiconEntry",
    "PhoneticResult",
    "normalize_text_for_hash",
    "sha256_normalized",
]
