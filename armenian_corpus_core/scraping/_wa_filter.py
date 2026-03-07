"""Lightweight Western Armenian language filter.

Provides ``is_western_armenian(text)`` — the same API the scrapers rely on
to filter downloaded documents.  Implements a multi-signal scoring algorithm
that combines:

1. Classical orthographic markers retained by WA but reformed away by EA
   (Soviet orthographic reforms 1922-1940).
2. WA-specific lexical and grammatical markers.
3. WA-specific vocabulary.
4. Eastern Armenian reform markers (negative signal).
5. Word-internal classical-orthography patterns.

This is a self-contained copy of the scoring logic from
``WesternArmenianLLM/src/cleaning/language_filter.py``, stripped of
author-database and config-file dependencies so it can be used as an
optional filter by any scraper in this package.
"""

from __future__ import annotations

import re


# == 1. Classical-orthography markers =========================================

_CLASSICAL_ORTHO_MARKERS: list[tuple[str, float]] = [
    ("\u0565\u0561", 2.0),      # ea digraph (WA retains, EA reformed to ya)
    ("\u056B\u0582", 3.0),      # iw digraph (pervasive in WA, dropped by EA)
    ("\u0574\u0567\u057B", 2.5), # mej with long-e (WA classical)
    ("\u056B\u0582\u0580\u0561\u0584\u0561\u0576\u0579\u056B\u0582\u0580", 4.0),  # iwrakanchiwer
    ("\u056C\u0565\u0566\u0578\u0582", 1.5),  # lezou
    ("\u0578\u0575", 2.0),      # oy diphthong (classical)
]

# == 2. WA-specific lexical / grammatical markers =============================

_LEXICAL_MARKERS: list[tuple[str, float]] = [
    ("\u056F\u0568", 2.0),          # ge (present tense prefix)
    ("\u056F\u055A", 2.0),          # g' (elided before vowel)
    ("\u057A\u056B\u057F\u056B", 2.0),  # bidi (WA future marker)
    ("\u0570\u0578\u0576", 3.0),    # hon (WA "there")
    ("\u0570\u0578\u057D", 3.0),    # hos (WA "here")
    ("\u0561\u056C", 1.0),          # al (WA "also/too")
    ("\u0570\u056B\u0574\u0561", 2.0),  # hima (WA "now")
    ("\u0561\u0575\u057D\u057A\u0567\u057D", 2.5),  # aysbes (WA "like this")
    ("\u0561\u0575\u0576\u057A\u0567\u057D", 2.5),  # aynbes (WA "like that")
    ("\u0578\u0579\u056B\u0576\u0579", 2.5),  # vochinch (WA "nothing")
    ("\u0562\u0561\u0576 \u0574\u0568", 2.0),  # pan me (WA "something")
    ("\u0579\u0565\u0574", 2.0),    # chem (WA negative particle)
    ("\u0574\u0565\u0576\u0584", 2.0),  # menk (WA "we")
    ("\u056B\u056C", 1.5),          # il (infinitive suffix)
    ("\u0563\u0565\u0572\u0565\u0581\u056B\u056F", 1.5),  # keghetsig (WA "beautiful")
]

# == 2b. WA-specific vocabulary ===============================================

_WA_VOCABULARY: list[tuple[str, float]] = [
    ("\u0573\u0565\u0580\u0574\u0561\u056f", 3.0),  # jermag ("white")
    ("\u056d\u0578\u0570\u0561\u0576\u0578\u0581", 3.0),  # khohanots ("kitchen")
    ("\u0573\u0578\u0582\u0580", 2.5),  # jour ("water")
    ("\u0577\u0561\u057a\u056b\u056f", 3.0),  # shabig ("shirt")
    ("\u0574\u0561\u0576\u0579\u0578\u0582\u056f", 3.0),  # manchoug ("child")
    ("\u057f\u0572\u0561", 2.5),  # dgha ("boy")
    ("\u056d\u0585\u057d\u056b\u056c", 2.5),  # khosil ("to speak")
    ("\u0565\u0580\u0569\u0561\u056c", 2.5),  # yerthal ("to go")
    ("\u0568\u0576\u0565\u056c", 2.5),  # enel ("to do")
    ("\u0578\u0582\u0566\u0565\u056c", 2.5),  # ouzel ("to want")
    ("\u0570\u0561\u057d\u056f\u0576\u0561\u056c", 2.5),  # hasgnal ("to understand")
    ("\u0561\u0580\u0564\u0567\u0576", 2.5),  # artyen ("already")
    ("\u0570\u0561\u057a\u0561", 2.5),  # haba ("then/so")
    ("\u0577\u0561\u057f", 2.5),  # shad ("very/much")
    ("\u056f\u056b\u0580\u0561\u056f\u056b", 2.5),  # giragi ("Sunday")
]

# == 2c. Eastern Armenian reform markers (NEGATIVE signals) ===================

_EASTERN_ARMENIAN_REFORM_MARKERS: list[tuple[str, float]] = [
    ("\u0574\u056B\u0575", 2.0),  # miy (EA reformed digraph)
    ("\u056D\u0576\u0561\u0575\u0574", 2.0),  # khnaym (EA reformed)
]

# == Regex patterns ===========================================================

_WORD_INTERNAL_E_LONG_RE = re.compile(r"[\u0531-\u0587]\u0567[\u0531-\u0587]")

_WORD_ENDING_AY_RE = re.compile(
    r"\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)"
)
_WORD_ENDING_OY_RE = re.compile(
    r"\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)"
)

# == Threshold ================================================================

WA_SCORE_THRESHOLD = 5.0


def _has_armenian_script(text: str, threshold: float = 0.2) -> bool:
    """Return True if at least *threshold* fraction of characters are Armenian."""
    if not text:
        return False
    armenian = sum(1 for c in text if "\u0530" <= c <= "\u058F")
    return armenian / len(text) >= threshold


def compute_wa_score(text: str) -> float:
    """Compute a weighted Western Armenian score for *text*.

    Higher score = stronger WA signal.  Combines positive (WA) and
    negative (EA reform) signals.
    """
    if not text:
        return 0.0

    score = 0.0

    # 1. Classical orthographic markers
    for marker, weight in _CLASSICAL_ORTHO_MARKERS:
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2. Lexical / grammatical markers
    for marker, weight in _LEXICAL_MARKERS:
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2b. WA-specific vocabulary
    for marker, weight in _WA_VOCABULARY:
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2c. Eastern Armenian reform markers (subtract)
    for marker, weight in _EASTERN_ARMENIAN_REFORM_MARKERS:
        count = text.count(marker)
        if count:
            score -= weight * min(count, 10)

    # 3. Word-internal long-e (classical orthography signal)
    internal_hits = len(_WORD_INTERNAL_E_LONG_RE.findall(text))
    if internal_hits:
        score += 1.0 * min(internal_hits, 20)

    # 3b. Word-final diphthongs -ay and -oy (classical orthography)
    ay_hits = len(_WORD_ENDING_AY_RE.findall(text))
    oy_hits = len(_WORD_ENDING_OY_RE.findall(text))
    if ay_hits:
        score += 1.5 * min(ay_hits, 15)
    if oy_hits:
        score += 2.0 * min(oy_hits, 15)

    return score


def is_western_armenian(text: str, threshold: float | None = None) -> bool:
    """Determine if *text* is Western Armenian using multi-signal scoring.

    Parameters
    ----------
    text:
        Input document text.
    threshold:
        Minimum score to classify as WA.  Defaults to ``WA_SCORE_THRESHOLD``.

    Returns
    -------
    True if the text scores above the threshold.
    """
    if not _has_armenian_script(text):
        return False
    thresh = threshold if threshold is not None else WA_SCORE_THRESHOLD
    return compute_wa_score(text) >= thresh
