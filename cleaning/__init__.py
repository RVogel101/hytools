"""Text cleaning pipeline for Western Armenian corpus.

Core utilities for normalizing, deduplicating, and filtering Armenian text.
"""

from .normalizer import normalize, normalize_unicode, normalize_whitespace, remove_junk_lines
from .armenian_tokenizer import (
    decompose_ligatures,
    armenian_lowercase,
    normalize as tokenizer_normalize,
    extract_words,
    word_frequencies,
    file_frequencies,
)
from .author_database import (
    Dialect,
    GeographicRegion,
    AuthorRecord,
    WESTERN_ARMENIAN_AUTHORS,
    EASTERN_ARMENIAN_AUTHORS,
    infer_dialect_from_region,
    lookup_author,
    get_authors_by_dialect,
    detect_author_from_text,
)
from .language_filter import (
    is_armenian,
    compute_wa_score,
    WA_SCORE_THRESHOLD,
)
from .dedup import deduplicate_files
from ingestion._shared.helpers import is_western_armenian

__all__ = [
    # Normalizer
    "normalize",
    "normalize_unicode",
    "normalize_whitespace",
    "remove_junk_lines",
    # Tokenizer
    "decompose_ligatures",
    "armenian_lowercase",
    "tokenizer_normalize",
    "extract_words",
    "word_frequencies",
    "file_frequencies",
    # Author database
    "Dialect",
    "GeographicRegion",
    "AuthorRecord",
    "WESTERN_ARMENIAN_AUTHORS",
    "EASTERN_ARMENIAN_AUTHORS",
    "infer_dialect_from_region",
    "lookup_author",
    "get_authors_by_dialect",
    "detect_author_from_text",
    # Language filter
    "is_armenian",
    "compute_wa_score",
    "WA_SCORE_THRESHOLD",
    # Dedup
    "deduplicate_files",
    # WA classifier (re-export from ingestion._shared.helpers)
    "is_western_armenian",
]
