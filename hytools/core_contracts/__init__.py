"""Core domain contracts for migration-safe integration."""

from .hashing import normalize_text_for_hash, sha256_normalized
from .types import DocumentRecord, LexiconEntry, PhoneticResult

# `DialectTag` is legacy; new workflows should use `internal_language_code` /
# `internal_language_branch` exclusively. Keep type in source for backward
# compatibility within the module, but do not export by default.
__all__ = [
    "DocumentRecord",
    "LexiconEntry",
    "PhoneticResult",
    "normalize_text_for_hash",
    "sha256_normalized",
]
