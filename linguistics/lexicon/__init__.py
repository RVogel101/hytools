"""Lexicon and etymology: loanword detection, etymology storage (MongoDB)."""

from . import etymology_db
from . import loanword_tracker

# Re-export main public API for backward compatibility
from .loanword_tracker import (
    LoanwordReport,
    PossibleLoanwordReport,
    analyze_loanwords,
    analyze_possible_loanwords,
    analyze_batch,
    get_loanword_lexicon,
    add_loanwords,
    normalize_lexicon_word,
)
from .etymology_db import (
    SOURCE_WIKTIONARY,
    SOURCE_NAYIRI,
    SOURCE_MANUAL,
    normalize_lemma,
    import_etymology_from_wiktextract,
)

__all__ = [
    "etymology_db",
    "loanword_tracker",
    "LoanwordReport",
    "PossibleLoanwordReport",
    "analyze_loanwords",
    "analyze_possible_loanwords",
    "analyze_batch",
    "get_loanword_lexicon",
    "add_loanwords",
    "normalize_lexicon_word",
    "SOURCE_WIKTIONARY",
    "SOURCE_NAYIRI",
    "SOURCE_MANUAL",
    "normalize_lemma",
    "import_etymology_from_wiktextract",
]
