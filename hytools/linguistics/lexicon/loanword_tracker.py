"""Loanword detection and tracking for Armenian text.

Identifies loanwords by source language (Russian, Turkish, Arabic, Farsi,
French, Spanish, etc.) to support:
1. Dialect/region inference (Russian → EA/Armenia; Arabic/Turkish/French → WA/diaspora)
2. Per-text loanword counts and unique lists for ingestion metrics
3. Corpus-level loanword statistics

Loanword lists are extensible; see LOANWORD_SOURCES in this module.

Lexicons are stored as Python sets; each word is Armenian script (lowercase,
NFC-normalized). Normalization follows cleaning.armenian_tokenizer.
"""

from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

try:
    from hytools.cleaning.armenian_tokenizer import extract_words, normalize as _tokenizer_normalize
except ImportError:
    import re

    _ARMENIAN_RE = re.compile(r"[\u0531-\u0556\u0561-\u0587]+")

    def extract_words(text: str, min_length: int = 2) -> list[str]:
        """Fallback: extract Armenian words if cleaning module unavailable."""
        text = unicodedata.normalize("NFC", text)
        words = _ARMENIAN_RE.findall(text.lower())
        return [w for w in words if len(w) >= min_length]

    def _tokenizer_normalize(text: str) -> str:
        """Fallback: NFC + Armenian lowercase when cleaning not available."""
        text = unicodedata.normalize("NFC", text)
        chars = []
        for c in text:
            cp = ord(c)
            if 0x0531 <= cp <= 0x0556:
                chars.append(chr(cp + 0x30))
            else:
                chars.append(c)
        return "".join(chars)


def _normalize_lexicon_word(word: str) -> str:
    """Normalize a lexicon entry to match tokenizer output (NFC, ligatures decomposed, lowercase)."""
    return _tokenizer_normalize(word.strip())


# Public alias for use by callers who want to normalize words like the lexicons.
normalize_lexicon_word = _normalize_lexicon_word


@dataclass
class LoanwordReport:
    """Per-text loanword analysis result."""

    text_id: str = ""
    source: str = ""
    total_words: int = 0
    total_loanwords: int = 0
    counts_by_language: dict[str, int] = field(default_factory=dict)
    unique_loanwords: list[str] = field(default_factory=list)
    loanwords_by_language: dict[str, list[str]] = field(default_factory=dict)

    def loanword_ratio(self) -> float:
        """Fraction of words that are loanwords (0.0–1.0)."""
        if self.total_words == 0:
            return 0.0
        return self.total_loanwords / self.total_words

    def to_dict(self) -> dict:
        """Serialize to plain dict for storage/metrics."""
        return {
            "text_id": self.text_id,
            "source": self.source,
            "total_words": self.total_words,
            "total_loanwords": self.total_loanwords,
            "loanword_ratio": round(self.loanword_ratio(), 4),
            "counts_by_language": dict(self.counts_by_language),
            "unique_loanwords": list(self.unique_loanwords),
            "loanwords_by_language": {
                lang: list(words)
                for lang, words in self.loanwords_by_language.items()
            },
        }


@dataclass
class PossibleLoanwordReport:
    """Per-text *possible* loanword analysis based on dictionary coverage.

    This flags Armenian tokens that are **not** found in a reference
    Armenian lexicon (e.g. Nayiri, custom WA dictionary). It does *not*
    attempt to guess the source language; it is intended for expert review.
    """

    text_id: str = ""
    source: str = ""
    total_words: int = 0
    total_possible_loanwords: int = 0
    possible_loanword_counts: dict[str, int] = field(default_factory=dict)
    unique_possible_loanwords: list[str] = field(default_factory=list)

    def possible_loanword_ratio(self) -> float:
        """Fraction of words that are flagged as possible loanwords."""
        if self.total_words == 0:
            return 0.0
        return self.total_possible_loanwords / self.total_words

    def to_dict(self) -> dict:
        """Serialize to plain dict for storage/metrics."""
        return {
            "text_id": self.text_id,
            "source": self.source,
            "total_words": self.total_words,
            "total_possible_loanwords": self.total_possible_loanwords,
            "possible_loanword_ratio": round(self.possible_loanword_ratio(), 4),
            "possible_loanword_counts": dict(self.possible_loanword_counts),
            "unique_possible_loanwords": list(self.unique_possible_loanwords),
        }


# ═════════════════════════════════════════════════════════════════════════════
#  Loanword lexicons (Armenian script, lowercase, NFC-normalized)
#  Extensible: add entries or load from external JSON/TSV. All entries are
#  normalized via cleaning.armenian_tokenizer (NFC, ligature decomposition, lowercase).
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
#  Loanword lexicons (Armenian script, lowercase, NFC-normalized)
#  Entries normalized via cleaning.armenian_tokenizer for consistent lookup.
# ═════════════════════════════════════════════════════════════════════════════

def _build_normalized_set(raw_words: Iterable[str]) -> set[str]:
    """Build a set of normalized Armenian words for lexicon lookup."""
    return {_normalize_lexicon_word(w) for w in raw_words if w.strip()}

# Russian-origin (EA: Armenia, former USSR) — Wiktionary Category:Armenian terms borrowed from Russian
_LOANWORDS_RUSSIAN: set[str] = _build_normalized_set([
    "ապարատ", "ավտոբուս", "ավտո", "բուրժուա", "տուրիստ", "էքսկլավ", "անկլավ",
    "կոնֆլիկտ", "մոլեկուլ", "լիմոնադ", "խամոն", "խալտուրա", "գիլյոտին",
    "ասֆալտ", "ալմանախ", "ակտիվ", "ակորդեոն", "արգումենտ", "ասոցիացիա",
    "ամբիցիա", "անգինա", "անեկդոտ", "աքսեսուար", "աուդիտոր", "սցենար",
    "մեբել", "էվֆեմիզմ", "դիստրիբյուտոր", "վեդրո", "ապենդիցիտ", "ատեստատ",
    "ասպիրանտ", "ասպեկտ", "ավիացիա", "ավտոպարկ",
])

# Turkish-origin (WA: Ottoman diaspora)
_LOANWORDS_TURKISH: set[str] = _build_normalized_set([
    "բալիկ", "չախմախ", "կրպակ", "դուգարա", "թաղ", "խաշ", "պասպորտ",
    "շիշ", "կաթի", "ֆիսք", "պատրոն", "թաս", "սուփա", "խորան", "թամամ",
])

# Arabic-origin (WA: Lebanon, Syria, Iraq)
_LOANWORDS_ARABIC: set[str] = _build_normalized_set([
    "քաթիպ", "սուլթան", "քաֆէ", "բաբ", "սուք", "մուլլա", "վագիֆ",
    "քադի", "ամիր", "խալիֆ", "մաշրիկ", "մահրիք", "ֆեթուա",
])

# French-origin (WA: Lebanon, France)
_LOANWORDS_FRENCH: set[str] = _build_normalized_set([
    "բուֆէ", "պարֆեմ", "սալոն", "պարի", "տակսի", "պիես", "թատրոն",
    "բալետ", "կուրս", "մենյու", "մետրո", "ատելիե", "կաբինետ",
])

# Spanish-origin (WA: Argentina diaspora)
_LOANWORDS_SPANISH: set[str] = _build_normalized_set([
    "տանգո", "պասիո", "ֆիեստա", "մատէ", "կարամել", "կասա", "պլազա",
])

# Modern Farsi/Persian (EA: Iran)
_LOANWORDS_FARSI: set[str] = _build_normalized_set([
    "բաղչա", "պարսկերեն", "շահ", "մեյդան", "կաբաբ",
])

# Source language → word set
_LOANWORD_LEXICONS: dict[str, set[str]] = {
    "russian": _LOANWORDS_RUSSIAN,
    "turkish": _LOANWORDS_TURKISH,
    "arabic": _LOANWORDS_ARABIC,
    "french": _LOANWORDS_FRENCH,
    "spanish": _LOANWORDS_SPANISH,
    "farsi": _LOANWORDS_FARSI,
}


def _build_word_to_language_map() -> dict[str, str]:
    """Map each loanword to its source language (first occurrence wins)."""
    word_to_lang: dict[str, str] = {}
    for lang, words in _LOANWORD_LEXICONS.items():
        for w in words:
            if w not in word_to_lang:
                word_to_lang[w] = lang
    return word_to_lang


_WORD_TO_LANGUAGE = _build_word_to_language_map()


def _default_is_known_armenian_word(word: str) -> bool:
    """Placeholder Armenian dictionary check.

    Currently always returns True (treats all tokens as known Armenian).
    To enable real dictionary-backed detection (e.g. Nayiri), replace
    this function or pass a custom *is_known_word* predicate into
    ``analyze_possible_loanwords``.
    """
    return True


def analyze_loanwords(
    text: str,
    text_id: str = "",
    source: str = "",
) -> LoanwordReport:
    """Detect loanwords in *text* and return a per-text report.

    Args:
        text: Armenian text to analyze
        text_id: Optional document ID for the report
        source: Optional source label (e.g. "loc", "wikipedia")

    Returns:
        LoanwordReport with counts by language, unique loanwords, and ratios.
    """
    words = extract_words(text, min_length=2)
    total = len(words)

    counts: dict[str, int] = defaultdict(int)
    by_lang: dict[str, list[str]] = defaultdict(list)

    for w in words:
        lang = _WORD_TO_LANGUAGE.get(w)
        if lang:
            counts[lang] += 1
            if w not in by_lang[lang]:
                by_lang[lang].append(w)

    unique = sorted(set(w for w in words if w in _WORD_TO_LANGUAGE))
    total_loan = sum(counts.values())

    return LoanwordReport(
        text_id=text_id,
        source=source,
        total_words=total,
        total_loanwords=total_loan,
        counts_by_language=dict(counts),
        unique_loanwords=unique,
        loanwords_by_language=dict(by_lang),
    )


def analyze_possible_loanwords(
    text: str,
    text_id: str = "",
    source: str = "",
    is_known_word: Callable[[str], bool] | None = None,
) -> PossibleLoanwordReport:
    """Flag tokens that are not found in an Armenian dictionary.

    Args
    ----
    text:
        Armenian text to analyze (tokenized with ``extract_words``)
    text_id:
        Optional document ID for the report
    source:
        Optional source label (e.g. \"loc\", \"wikipedia\")
    is_known_word:
        Optional predicate ``is_known_word(token) -> bool`` that returns
        True if *token* is a known Armenian word. When omitted, a
        placeholder implementation is used (treats all words as known),
        so no possible loanwords are flagged.

    Returns
    -------
    PossibleLoanwordReport
        With counts and unique list of tokens not recognized as Armenian.
    """
    check = is_known_word or _default_is_known_armenian_word

    words = extract_words(text, min_length=2)
    total = len(words)

    unknown_counter: Counter[str] = Counter()
    for w in words:
        if not check(w):
            unknown_counter[w] += 1

    total_unknown = sum(unknown_counter.values())
    unique_unknown = sorted(unknown_counter.keys())

    return PossibleLoanwordReport(
        text_id=text_id,
        source=source,
        total_words=total,
        total_possible_loanwords=total_unknown,
        possible_loanword_counts=dict(unknown_counter),
        unique_possible_loanwords=unique_unknown,
    )


def analyze_batch(
    texts: Iterable[tuple[str, str, str]],
) -> list[LoanwordReport]:
    """Analyze multiple texts. Each item: (text, text_id, source)."""
    return [
        analyze_loanwords(text, text_id=tid, source=src)
        for text, tid, src in texts
    ]


def get_loanword_lexicon(language: str) -> set[str]:
    """Return the loanword set for a given source language."""
    return _LOANWORD_LEXICONS.get(language, set()).copy()


def add_loanwords(language: str, words: Iterable[str]) -> None:
    """Add loanwords to a language lexicon. Words are normalized (NFC, lowercase) before storage."""
    normalized = {_normalize_lexicon_word(w) for w in words if w.strip()}
    lang_set = _LOANWORD_LEXICONS.get(language)
    if lang_set is None:
        _LOANWORD_LEXICONS[language] = set(normalized)
    else:
        lang_set.update(normalized)
    # Rebuild map
    global _WORD_TO_LANGUAGE
    _WORD_TO_LANGUAGE = _build_word_to_language_map()


__all__ = [
    "LoanwordReport",
    "PossibleLoanwordReport",
    "analyze_loanwords",
    "analyze_possible_loanwords",
    "analyze_batch",
    "get_loanword_lexicon",
    "add_loanwords",
    "normalize_lexicon_word",
]
