"""Shared domain contracts for cross-project migration.

These types are intentionally dependency-light so the central package can be
used by downstream projects without side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class DialectTag(str, Enum):
    """Dialect classification for text and lexicon records."""

    WESTERN_ARMENIAN = "western_armenian"
    EASTERN_ARMENIAN = "eastern_armenian"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DocumentRecord:
    """Canonical normalized corpus document contract."""

    document_id: str
    source_family: str
    text: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    content_hash: Optional[str] = None
    char_count: Optional[int] = None
    internal_language_code: Optional[str] = None
    internal_language_branch: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LexiconEntry:
    """Canonical lexicon/vocabulary contract across projects."""

    lemma: str
    translation: Optional[str] = None
    pos: Optional[str] = None
    pronunciation: Optional[str] = None
    frequency_rank: Optional[int] = None
    syllable_count: Optional[int] = None
    internal_language_code: Optional[str] = None
    internal_language_branch: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PhoneticResult:
    """Canonical phonetic transcription contract."""

    word: str
    ipa: str
    english_approx: str
    max_phonetic_difficulty: float
    metadata: Dict[str, Any] = field(default_factory=dict)
