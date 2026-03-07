"""Language detection and filtering for Western Armenian text.

Separates Western Armenian documents from Eastern Armenian, English, and
other languages.  Uses a multi-signal scoring algorithm combining:

1. Classical orthographic markers retained by WA but reformed away by EA
   (Soviet orthographic reforms of 1922-1940).
2. WA-specific lexical and grammatical markers.
3. Known Western Armenian authors (diaspora literary figures).
4. Known Western Armenian publication cities (diaspora centres).

A document receives a weighted score from all signals.  If the score
exceeds a configurable threshold the document is classified as Western
Armenian.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml  # type: ignore[reportMissingModuleSource]

from .author_database import (
    Dialect,
    detect_author_from_text,
    get_authors_by_dialect,
)

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"

# == 1. Classical-orthography markers =========================================
#
# The Soviet orthographic reforms (1922 Abeghyan, finalised 1940) changed
# Armenian spelling in Soviet Armenia.  The diaspora (Western Armenian)
# rejected these reforms and continues to use classical orthography.
#
# Each tuple: (substring, per-occurrence weight)
# Higher weight = stronger WA signal.

_CLASSICAL_ORTHO_MARKERS: list[tuple[str, float]] = [
    # ea digraph -- classical spelling, WA retains it.
    # EA reformed ea -> ya.
    # e.g. WA miasin vs EA miyasin
    ("\u0565\u0561", 2.0),

    # iw digraph -- classical, pervasive in WA.
    # EA reformed spelling dropped this digraph entirely.
    ("\u056B\u0582", 3.0),

    # mej with long-e -- CO spelling of "inside".
    # EA reformed to mej with short-e.
    ("\u0574\u0567\u057B", 2.5),

    # NOTE: The ew ligature (\u0587 = yev = "and") is NOT a WA marker.
    # Both varieties use it as the word "and", but EA also uses it
    # word-internally to spell "yev" sounds, whereas WA spells those
    # out as \u0565 + \u0582.  Word-internal \u0587 is an EA signal,
    # but absence is hard to score, so we omit it here.

    # iwrakanchiwer = "each/every" -- very strong WA classical word
    ("\u056B\u0582\u0580\u0561\u0584\u0561\u0576\u0579\u056B\u0582\u0580", 4.0),

    # lezou = "language/tongue" with CO spelling
    ("\u056C\u0565\u0566\u0578\u0582", 1.5),

    # oy diphthong -- classical orthography retains this.
    # EA reformed spelling often reduces or replaces it.
    ("\u0578\u0575", 2.0),
]

# == 2. WA-specific lexical / grammatical markers =============================
#
# Grammatical constructions and vocabulary unique to or strongly associated
# with Western Armenian.

_LEXICAL_MARKERS: list[tuple[str, float]] = [
    # Present-tense verbal prefix
    ("\u056F\u0568", 2.0),          # ge (present tense prefix)
    ("\u056F\u055A", 2.0),          # g' (elided before vowel)

    # WA future marker
    ("\u057A\u056B\u057F\u056B", 2.0),  # bidi

    # WA "there" (EA: ayndegh)
    ("\u0570\u0578\u0576", 3.0),    # hon

    # WA "here" (EA: aystegh)
    ("\u0570\u0578\u057D", 3.0),    # hos

    # WA "also/too" (EA: el)
    ("\u0561\u056C", 1.0),          # al (very common, lower weight)

    # WA "now" (EA: hima -- same but WA usage is more common)
    ("\u0570\u056B\u0574\u0561", 2.0),  # hima

    # WA "like this" (EA: aysbes)
    ("\u0561\u0575\u057D\u057A\u0567\u057D", 2.5),  # aysbes (with long-e = CO)

    # WA "like that" (EA: aynbes)
    ("\u0561\u0575\u0576\u057A\u0567\u057D", 2.5),  # aynbes (with long-e = CO)

    # WA "nothing" (EA: vochinch)
    ("\u0578\u0579\u056B\u0576\u0579", 2.5),  # vochinch

    # WA "something" (EA: inchvor ban)
    ("\u0562\u0561\u0576 \u0574\u0568", 2.0),  # pan me

    # WA negative particle (EA: chem)
    ("\u0579\u0565\u0574", 2.0),    # chem

    # WA "we" (EA: menk)
    ("\u0574\u0565\u0576\u0584", 2.0),  # menk

    # WA infinitive suffix -il (EA does not have this conjugation class)
    ("\u056B\u056C", 1.5),          # il (e.g. khosil, hasgnil)

    # WA "beautiful"
    ("\u0563\u0565\u0572\u0565\u0581\u056B\u056F", 1.5),  # keghetsig
]

# == 2b. WA-specific vocabulary ==============================================
#
# Everyday words that differ between WA and EA.  These are strong
# indicators because they are common and clearly divergent.

_WA_VOCABULARY: list[tuple[str, float]] = [
    # Colours
    ("\u0573\u0565\u0580\u0574\u0561\u056f", 3.0),                      # jermag = "white" (EA: sbidag/spitak)

    # Food / household
    ("\u0561\u0576\u0571\u0565\u057c\u0578\u0581\u056b\u056f", 3.5),  # andzerrotsig = "napkin" (EA: antserots)
    ("\u056d\u0578\u0570\u0561\u0576\u0578\u0581", 3.0),              # khohanots = "kitchen"
    ("\u0573\u0578\u0582\u0580", 2.5),                                    # jour = "water" (EA: djur)

    # Body / clothing
    ("\u0577\u0561\u057a\u056b\u056f", 3.0),                             # shabig = "shirt" (EA: shapik)

    # People / family
    ("\u0574\u0561\u0576\u0579\u0578\u0582\u056f", 3.0),               # manchoug = "child" (EA: mankik)
    ("\u057f\u0572\u0561", 2.5),                                            # dgha = "boy" (EA: tgha)

    # Common verbs / expressions
    ("\u056d\u0585\u057d\u056b\u056c", 2.5),                             # khosil = "to speak"
    ("\u0565\u0580\u0569\u0561\u056c", 2.5),                             # yerthal = "to go" (EA: gnal)
    ("\u0568\u0576\u0565\u056c", 2.5),                                    # enel = "to do" (EA: anel)
    ("\u0578\u0582\u0566\u0565\u056c", 2.5),                             # ouzel = "to want" (EA: uzum em)
    ("\u0570\u0561\u057d\u056f\u0576\u0561\u056c", 2.5),               # hasgnal = "to understand"

    # WA-specific particles
    ("\u0561\u0580\u0564\u0567\u0576", 2.5),                             # artyen = "already" (EA: ardeyen)
    ("\u0570\u0561\u057a\u0561", 2.5),                                    # haba = "then/so" (WA colloquial)
    ("\u0577\u0561\u057f", 2.5),                                            # shad = "very/much" (WA pronunciation)

    # Days / time (CO spellings)
    ("\u056f\u056b\u0580\u0561\u056f\u056b", 2.5),                      # giragi = "Sunday" (EA: kiraki)
    ("\u0565\u0580\u056f\u0578\u0582\u0577\u0561\u0562\u0569\u056b", 2.5),  # yergoushabti = "Monday"
]

# == 2c. East Armenian post-1922 reform markers ==================================
#
# The Soviet orthographic reforms (1922-1940) replaced classical spellings
# with simplified forms.  These are strong EA signals and should lower WA score.
# Each tuple: (reformed_substring, classical_equivalent, per-occurrence_weight)

_EAST_ARMENIAN_REFORMS: list[tuple[str, str, float]] = [
    # ya digraph (EA reform) vs ea (CO/WA)
    # e.g., EA miyasin vs WA miasin
    ("\u0575\u0561", "\u0565\u0561", 2.0),

    # Removed iw digraph entirely (EA reform)
    # e.g., EA pi vs WA piw
    # (Hard to score direct presence, but absence is meaningful)

    # Short-e spelling in words like "mej" (EA reform)
    # e.g., EA mej vs WA mej with long-e
    # (Context-dependent, covered by regex below)

    # ay/oy diphthong reduction (EA reform) -- replacements
    # e.g., EA ai vs WA ay (rare, more context-dependent)

    # Note: These patterns are harder to score than WA markers because
    # they require understanding context (e.g., a word with ya might not
    # always be EA reformed).  The approach is to look for high frequency
    # of certain EA-specific patterns combined with LOW frequency of
    # classical patterns.
]

# == 2d. Known East Armenian authors (Soviet/Yerevan literary figures) =========
#
# PLANNED FUTURE FEATURE: Track Eastern Armenian authors to detect when
# they are writing in Western Armenian incorrectly (mixing dialects).
# This helps catch documents with code-switching or incorrect WA usage.
#
# Examples of well-known EA authors (for future reference):
# - Հովհաննես Թուման (Hovhannes Tumanyan)
# - Առաբա (Arawba/Zardaryan)
# - Վահան Թերյան (Vahan Teryan)
# - Ծեղين Դավտյան (Tseghin Davtyan)
# - Գրիգոր Նաբար (Grigor Nebar)
#
# ACTION ITEMS:
# 1. Build a database of EA authors and their works (from Soviet Armenian literary canon)
# 2. When an EA author is detected, flag mixed-dialect usage more aggressively
# 3. Use author lexical fingerprints (EA-specific vocabulary they use frequently)
#
# For now, this is documented as a TODO for future enhancement.

# == 2c. Eastern Armenian reform markers (NEGATIVE signals) ===================
#
# The Soviet orthographic reforms (1922-1940) changed Eastern Armenian spelling.
# If text contains many of these REFORMED spellings, it's likely EA, not WA.
# This is scored NEGATIVELY to reduce WA confidence.
#
# Each tuple: (substring, per-occurrence penalty weight)
# Higher weight = stronger EA signal.

_EASTERN_ARMENIAN_REFORM_MARKERS: list[tuple[str, float]] = [
    # ea -> ya reform (EA spelling)
    # WA: miasin, WA: միասին (mi-a-sin)
    # EA: miyasin, EA: միայն (mi-ya-sin)
    # The reformed spelling "miyay" digraph is EA-specific
    ("\u0574\u056B\u0575", 2.0),    # miy (part of reformed miyasin)

    # khnum -> khanaim reform pattern
    # WA retains classical forms with 'nu'
    # EA reformed to modern 'na'
    ("\u056D\u0578\u0582\u0570", -0.5),  # khouh (WA classical, so NEGATIVE penalty = OK)
    ("\u056D\u0576\u0561\u0575\u0574", 2.0),  # khnaym (EA reformed)

    # akousl/akhosk reform (dative endings)
    # WA: -akann, -akan
    # EA reformed various forms away
    # This is subtle; marking more obvious patterns

    # Presence of short-e where WA would use long-e
    # This is caught by _WORD_INTERNAL_E_LONG_RE absence
    # (fewer WA markers already penalizes this)

    # Specific EA verbs from reform period
    # GA- prefix reduced/eliminated in some contexts (EA tendency)
    # WA: gal, ganal (go, take)
    # EA often uses just al, anal in 3rd person contexts
    # Pattern: reduced verbal forms

    # EA-specific particle: chem (negation, more formal EA)
    # WA: shem/chem but different distribution
    # Not a perfect marker, so low weight
]

# == 3. Known EA authors (Soviet Armenian literary canon) =====================
#
# When these author names are detected, flag for potential dialect mixing.
# If an EA author is detected + text cannot verify as pure WA → suspicious.
# This is meant for FUTURE implementation to track author authority.
#
# For now, this helps document who writes in which tradition.

_EAST_ARMENIAN_AUTHORS: list[tuple[str, float]] = [
    # TODO: Populate with known EA authors from Soviet Armenia
    # Examples (to be verified and expanded):
    # ("Հայրենիկ Կաչոճյան", -3.0),  # Hairenik Kachochyan (EA)
    # ("Հարութ Հայրապետյան", -3.0),  # Harut Hayrapetyan (EA)
    # When implemented with real data, these should reduce WA score
]

# == 4. Known WA authors (diaspora literary figures) ==========================
#
# If a document mentions these names it is very likely Western Armenian.
# Names are given in Armenian script as they appear in WA texts.
# ONLY diaspora / Western Armenian figures are included here.

_WA_AUTHORS: list[tuple[str, float]] = [
    # Classical / foundational
    ("\u0544\u0565\u056D\u056B\u0569\u0561\u0580", 5.0),       # Mekhitar (Mekhitarists)
    ("\u0544\u056D\u056B\u0569\u0561\u0580\u0565\u0561\u0576", 5.0),  # Mekhitarean

    # 19th-20th century WA literary figures
    ("\u054F\u0561\u0576\u056B\u0567\u056C", 4.0),             # Taniel (Varoujan)
    ("\u054E\u0561\u0580\u0578\u0582\u056A\u0561\u0576", 5.0), # Varoujan
    ("\u054D\u056B\u0561\u0574\u0561\u0576\u0569\u0578", 5.0), # Siamanto
    ("\u0536\u0561\u0580\u056B\u0586\u0565\u0561\u0576", 4.0), # Zarifean
    ("\u054F\u0565\u0584\u0567\u0565\u0561\u0576", 5.0),       # Tekeyan
    ("\u0546\u056B\u056F\u0578\u0572\u0578\u057D", 4.0),       # Nikoghos (Sarafian etc.)
    ("\u054D\u0561\u0580\u0561\u0586\u0565\u0561\u0576", 5.0), # Sarafian
    ("\u0547\u0561\u0570\u0561\u0576", 3.0),                   # Shahan (Shahnour etc.)
    ("\u0547\u0561\u0570\u0576\u0578\u0582\u0580", 5.0),       # Shahnour
    ("\u0546\u056B\u056F\u0578\u0572\u0561\u0575\u0578\u057D", 4.0),  # Nikoghayos
    ("\u0531\u0563\u0578\u0576\u0581", 3.0),                   # Agonts
    ("\u0536\u0561\u0580\u0564\u0561\u0580\u0565\u0561\u0576", 5.0),  # Zardarian
    ("\u0555\u0577\u0561\u056F\u0561\u0576", 5.0),             # Oshakan
    ("\u0536\u0561\u057A\u0567\u056C", 4.0),                   # Zabel (Yesayan)
    ("\u0535\u057D\u0561\u0575\u0565\u0561\u0576", 5.0),       # Yesayan
    ("\u0540\u0561\u0574\u0561\u057D\u057F\u0565\u0572", 4.0), # Hamastegh
    ("\u0546\u0578\u0580\u0561\u0575\u0580", 4.0),             # Norayr
    ("\u054A\u0565\u0577\u056B\u056F\u0569\u0561\u0577\u056C\u0565\u0561\u0576", 5.0),  # Beshiktashlean
    ("\u054A\u0565\u0577\u056B\u056F\u0569\u0561\u0577\u056C\u056B\u0561\u0576", 5.0),  # Beshiktashlian (alternate)
    ("\u054E\u0561\u0580\u0564\u0561\u0576\u0565\u0561\u0576", 4.0),  # Vardanean
    ("\u0531\u056C\u056B\u0577\u0561\u0576", 4.0),              # Alishan
    ("\u0539\u0578\u0583\u0579\u0565\u0561\u0576", 4.0),        # Topchean
    ("\u0536\u0578\u0570\u0580\u0561\u057A", 5.0),              # Zohrap
    ("\u0544\u056B\u057D\u0561\u0584\u0565\u0561\u0576", 4.0),  # Misakean
    ("\u054A\u0561\u0580\u0578\u0576\u0565\u0561\u0576", 4.0),  # Baronean
]

# == 4. Known WA publication cities (diaspora centres) ========================
#
# Mentions of these cities in Armenian script strongly suggest diaspora
# (Western Armenian) provenance.

_WA_PUBLICATION_CITIES: list[tuple[str, float]] = [
    ("\u054A\u0567\u0575\u0580\u0578\u0582\u0569", 4.0),       # Peyrouth (Beirut)
    ("\u054A\u0578\u056C\u056B\u057D", 3.0),                   # Bolis (Istanbul in WA)
    ("\u0553\u0561\u0580\u056B\u0566", 3.5),                   # Bariz (Paris)
    ("\u0543\u0561\u0570\u056B\u0580\u0567", 3.5),             # Gahireh (Cairo)
    ("\u054A\u0578\u057D\u0569\u0578\u0576", 3.0),             # Posdon (Boston)
    ("\u0546\u056B\u0582 \u0535\u0578\u0580\u0584", 3.5),      # Niw York (New York)
    ("\u053E\u0578\u0582\u0580\u056B\u056D", 3.0),             # Tsurikh (Zurich)
    ("\u053E\u0565\u0576\u0567\u0582", 3.0),                   # Tsenev (Geneva)
    ("\u054E\u056B\u0567\u0576\u0576\u0561", 3.0),             # Vienna
    ("\u054D\u0561\u0576 \u053C\u0561\u0566\u0561\u0580\u0578", 3.0),  # San Lazaro
    ("\u054E\u0565\u0576\u0565\u057F\u056B\u056F", 3.5),       # Venedig (Venice)
    ("\u0540\u0561\u056C\u0567\u057A", 4.0),                   # Halep (Aleppo)
    ("\u0531\u0576\u0569\u056B\u056C\u056B\u0561\u057D", 3.0), # Antilias
    ("\u053F\u056B\u056C\u056B\u056F\u056B\u0561", 3.0),       # Cilicia
    ("\u0544\u0561\u0580\u057D\u0567\u0575", 3.0),             # Marseille
    ("\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056C", 3.0), # Montreal
    ("\u053F\u0561\u0570\u056B\u0580\u0567", 3.5),             # Gahireh (Cairo alt spelling)
    ("\u0532\u0578\u0582\u0565\u0576\u0578\u057D \u0531\u0575\u0580\u0567\u057D", 3.5),  # Buenos Aires
    ("\u054D\u0561\u0576 \u054A\u0561\u0578\u0582\u056C\u0578", 3.0),  # San Paulo
]

# == Regex for word-internal long-e ============================================
# In classical orthography, long-e appears word-internally.
# The Soviet reform changed many word-internal long-e to short-e.
_WORD_INTERNAL_E_LONG_RE = re.compile(
    r"[\u0531-\u0587]\u0567[\u0531-\u0587]"
)

# == Regex for word-final diphthongs (classical orthography) ==================
# Words ending in -ay or -oy are characteristic of classical orthography
# (retained by WA).  EA reformed spelling often reduces these.
_WORD_ENDING_AY_RE = re.compile(
    r"\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)"
)
_WORD_ENDING_OY_RE = re.compile(
    r"\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)"
)

# Threshold: minimum score to classify a document as Western Armenian.
WA_SCORE_THRESHOLD = 5.0


def _has_armenian_script(text: str, threshold: float = 0.2) -> bool:
    """Return True if at least *threshold* fraction of characters are Armenian."""
    if not text:
        return False
    armenian = sum(1 for c in text if "\u0530" <= c <= "\u058F")
    return armenian / len(text) >= threshold


def is_armenian(text: str) -> bool:
    """Return True if *text* is primarily Armenian (Eastern or Western).

    Uses script-ratio detection as the primary signal since both Eastern and
    Western Armenian share the same Unicode block.
    """
    return _has_armenian_script(text)


def compute_wa_score(text: str) -> float:
    """Compute a weighted Western Armenian score for *text*.

    The score is the sum of per-occurrence weights across all signal
    categories.  A higher score means stronger WA signal.
    
    Includes both positive (WA markers) and negative (EA reform markers)
    signals to improve accuracy.
    """
    if not text:
        return 0.0

    score = 0.0

    # 1. Classical orthographic markers (POSITIVE: WA signal)
    for marker, weight in _CLASSICAL_ORTHO_MARKERS:
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2. Lexical / grammatical markers (POSITIVE: WA signal)
    for marker, weight in _LEXICAL_MARKERS:
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2b. WA-specific vocabulary (POSITIVE: WA signal)
    for marker, weight in _WA_VOCABULARY:
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2c. Eastern Armenian reform markers (NEGATIVE: EA signal)
    # Penalize text that contains EA-reformed spellings
    for marker, weight in _EASTERN_ARMENIAN_REFORM_MARKERS:
        count = text.count(marker)
        if count:
            score -= weight * min(count, 10)  # SUBTRACT to penalize EA markers

    # 3. Word-internal long-e (POSITIVE: classical orthography = WA signal)
    internal_hits = len(_WORD_INTERNAL_E_LONG_RE.findall(text))
    if internal_hits:
        score += 1.0 * min(internal_hits, 20)

    # 3b. Word-final diphthongs -ay and -oy (POSITIVE: classical orthography)
    ay_hits = len(_WORD_ENDING_AY_RE.findall(text))
    oy_hits = len(_WORD_ENDING_OY_RE.findall(text))
    if ay_hits:
        score += 1.5 * min(ay_hits, 15)
    if oy_hits:
        score += 2.0 * min(oy_hits, 15)

    # 4. Author names
    # Positive: WA authors boost score
    for name, weight in _WA_AUTHORS:
        if name in text:
            score += weight
    
    # Negative: EA authors reduce score (for future implementation)
    for name, weight in _EAST_ARMENIAN_AUTHORS:
        if name in text:
            score += weight  # weight is already negative

    # 5. Publication cities
    for city, weight in _WA_PUBLICATION_CITIES:
        if city in text:
            score += weight

    return score


def is_western_armenian(text: str, threshold: float | None = None) -> bool:
    """Determine if *text* is Western Armenian using multi-signal scoring.

    Combines classical-orthography markers, WA-specific grammar/vocabulary,
    known WA author names, and diaspora publication city names into a single
    weighted score.  Returns True if the score exceeds *threshold*.

    Parameters
    ----------
    text:
        Input document text.
    threshold:
        Minimum score to classify as WA.  Defaults to ``WA_SCORE_THRESHOLD``.
    """
    if not _has_armenian_script(text):
        return False

    thresh = threshold if threshold is not None else WA_SCORE_THRESHOLD
    return compute_wa_score(text) >= thresh


def detect_dialect_mixing_with_author(text: str) -> dict:
    """Detect potential dialect mixing based on author context.
    
    Checks if a known author is mentioned in the text, and if so,
    verifies that their dialect tradition matches the detected text dialect.
    This catches cases where an Eastern Armenian author attempts to write
    in Western Armenian without complete mastery.
    
    Parameters
    ----------
    text:
        Input document text to analyze
    
    Returns
    -------
    dict with keys:
        - author_detected: (AuthorRecord or None)
        - author_name: (str or None)
        - author_dialect: (str or None, e.g., "western", "eastern")
        - text_dialect: (str, "western" or "eastern" or "unknown")
        - dialect_mismatch: (bool, True if author dialect != text dialect)
        - confidence: (float, 0-1 indicating confidence in WA classification)
        - recommendation: (str, "ACCEPT", "FLAG", or "REJECT")
    """
    author_record, author_name = detect_author_from_text(text)
    
    # Compute text dialect with confidence score
    wa_score = compute_wa_score(text)
    is_wa = wa_score >= WA_SCORE_THRESHOLD
    text_dialect = "western" if is_wa else "eastern" if wa_score < 0 else "unknown"
    confidence = min(abs(wa_score) / 10.0, 1.0)  # Normalize to 0-1
    
    # Check for dialect mismatch with author
    dialect_mismatch = False
    recommendation = "ACCEPT"
    
    if author_record:
        dialect = author_record.dialect
        author_dialect = dialect.value if dialect is not None else None
        if dialect is not None and is_wa and dialect == Dialect.EASTERN:
            # EA author writing Western Armenian → potential issue
            dialect_mismatch = True
            recommendation = "FLAG" if confidence < 0.8 else "ACCEPT"
        elif dialect is not None and not is_wa and dialect == Dialect.WESTERN:
            # WA author but text reads as EA → contamination or misclassification
            dialect_mismatch = True
            recommendation = "FLAG"
    else:
        author_dialect = None
    
    return {
        "author_detected": author_record,
        "author_name": author_name,
        "author_dialect": author_dialect,
        "text_dialect": text_dialect,
        "dialect_mismatch": dialect_mismatch,
        "confidence": confidence,
        "wa_score": wa_score,
        "recommendation": recommendation,
    }


def filter_directory(
    input_dir: Path,
    output_dir: Path,
    require_western: bool = False,
    min_chars: int = 100,
) -> tuple[int, int]:
    """Copy Armenian (optionally Western-only) documents to *output_dir*.

    Parameters
    ----------
    input_dir:
        Directory of ``.txt`` files to filter.
    output_dir:
        Destination for passing documents.
    require_western:
        If True, only keep documents detected as Western Armenian.
    min_chars:
        Minimum character count; shorter documents are discarded.

    Returns
    -------
    tuple[int, int]
        ``(total, kept)``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.rglob("*.txt"))
    total = len(files)
    kept = 0

    for txt_file in files:
        text = txt_file.read_text(encoding="utf-8")
        if len(text) < min_chars:
            continue
        if not is_armenian(text):
            logger.debug("Non-Armenian, skipping: %s", txt_file.name)
            continue
        if require_western and not is_western_armenian(text):
            score = compute_wa_score(text)
            logger.debug(
                "Not Western Armenian (score=%.1f), skipping: %s",
                score, txt_file.name,
            )
            continue

        rel = txt_file.relative_to(input_dir)
        out = output_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        kept += 1

    logger.info("Language filter: %d / %d documents kept", kept, total)
    return total, kept


def run(config: dict | None = None) -> None:
    """Entry-point: filter the deduplicated corpus to Western Armenian only."""
    cfg = config or _load_config()
    dedup_dir = Path(cfg["paths"]["cleaned_dir"]).parent / "deduped"
    filtered_dir = Path(cfg["paths"]["cleaned_dir"]).parent / "filtered"
    min_chars: int = cfg["cleaning"]["min_chars_per_doc"]

    filter_directory(dedup_dir, filtered_dir, require_western=True, min_chars=min_chars)


def _load_config() -> dict:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()