"""
BGN/PCGN (1981) Armenian transliteration with Eastern, Classical, and Western variants,
and Armenian-to-IPA conversion for Western, Eastern, and Classical.

- Armenian → Latin (BGN/PCGN style): to_latin(text, dialect="western"|"eastern"|"classical")
- Latin → Armenian: to_armenian(roman_text, dialect=...)
- Armenian → IPA: to_ipa(text, dialect=...)

Supports full text: pass any string (word, sentence, or paragraph); non-Armenian characters
are left unchanged. See notebooks/transliteration_demo.ipynb for examples.

Uses modifier letter apostrophe (U+02BC) for aspirates: tʼ, chʼ, tsʼ, pʼ, kʼ.
Western: voicing reversal (բ→p, պ→b, ճ→j, ջ→ch, etc.); ու→"ou" (or "v" before vowel);
reverse: "u"→ը, "ou"/"oo"→ու.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

Dialect = Literal["eastern", "classical", "western"]

# BGN/PCGN aspirate character (modifier letter apostrophe)
ASPIRATE = "\u02BC"

# ─── Normalization (NFC + ligature decomposition) ───────────────────────
_LIGATURE_MAP = {
    "\uFB13": "\u0574\u0576",  # ﬓ → մն
    "\uFB14": "\u0574\u0565",  # ﬔ → մե
    "\uFB15": "\u0574\u056B",  # ﬕ → մի
    "\uFB16": "\u057E\u0576",  # ﬖ → վն
    "\uFB17": "\u0574\u056D",  # ﬗ → մխ
}


def _normalize_armenian(text: str) -> str:
    """NFC normalize and decompose Armenian ligatures; lowercase Armenian letters."""
    text = unicodedata.normalize("NFC", text)
    for lig, decomposed in _LIGATURE_MAP.items():
        text = text.replace(lig, decomposed)
    result = []
    for c in text:
        cp = ord(c)
        if 0x0531 <= cp <= 0x0556:
            result.append(chr(cp + 0x30))
        else:
            result.append(c)
    return "".join(result)


def _is_armenian_vowel(c: str) -> bool:
    return c in "աեէըիոյօ"


def _is_armenian_letter(c: str) -> bool:
    return c in _ARMENIAN_CONSONANTS or _is_armenian_vowel(c) or c == "յ" or c == "ւ"


def _get_armenian_word_bounds(text: str, i: int) -> tuple[int, int] | None:
    """Return (start, end) of the Armenian word containing index i, or None if text[i] is not Armenian."""
    if i < 0 or i >= len(text) or not _is_armenian_letter(text[i]):
        return None
    start = i
    while start > 0 and _is_armenian_letter(text[start - 1]):
        start -= 1
    end = i + 1
    while end < len(text) and _is_armenian_letter(text[end]):
        end += 1
    return (start, end)
_ARMENIAN_CONSONANTS = set("բգդզթժլխծկհձղճմնշչպջռսվտրցւփքֆ")


def _insert_unwritten_schwa_western(text: str) -> str:
    """
    Insert unwritten ը for Western Armenian pronunciation.
    - Word-initial ս when followed by any of կ, պ, տ, ք → ըս (as though ը existed before ս).
    - Between two consonants (no vowel in between) → insert ը between them.
    See docs/armenian_language_guids/PRONUNCIATION_RULES_MINED.md.
    """
    if not text or len(text) < 2:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    # Word-initial ս + (կ, պ, տ, or ք) → ըս + that consonant
    _S_FOLLOWED_BY = set("կպտք")
    while i < n:
        c = text[i]
        if i == 0 and c == "ս" and i + 1 < n and text[i + 1] in _S_FOLLOWED_BY:
            out.append("ը")
            out.append("ս")
            out.append(text[i + 1])
            i = 2
            continue
        out.append(c)
        # Don't break digraphs: if we're in ու or իւ, consume both
        if i + 1 < n:
            two = c + text[i + 1]
            if two == "ու" or two == "իւ":
                out.append(text[i + 1])
                i += 2
                continue
        # Between two consonants: insert ը
        if i + 1 < n and c in _ARMENIAN_CONSONANTS and text[i + 1] in _ARMENIAN_CONSONANTS:
            out.append("ը")
        i += 1
    return "".join(out)


# ─── BGN/PCGN base (Eastern) single-letter → Latin ───────────────────
# Source: BGN/PCGN 1981. Aspirates use ʼ (U+02BC).
_BGN_EASTERN: dict[str, str] = {
    "ա": "a", "բ": "b", "գ": "g", "դ": "d", "ե": "e", "զ": "z", "է": "e", "ը": "y",
    "թ": "t" + ASPIRATE, "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts", "կ": "k",
    "հ": "h", "ձ": "dz", "ղ": "gh", "ճ": "ch", "մ": "m", "յ": "y", "ն": "n", "շ": "sh",
    "ո": "o", "չ": "ch" + ASPIRATE, "պ": "p", "ջ": "j", "ռ": "rr", "ս": "s", "վ": "v",
    "տ": "t", "ր": "r", "ց": "ts" + ASPIRATE, "ւ": "w", "փ": "p" + ASPIRATE,
    "ք": "k" + ASPIRATE, "օ": "o", "ֆ": "f",
}

# Western: voicing reversal + affricate swap + ը→u (schwa), թ→tʼ (aspirate for round-trip)
_BGN_WESTERN: dict[str, str] = {
    "ա": "a", "բ": "p", "գ": "k", "դ": "t", "ե": "e", "զ": "z", "է": "e", "ը": "u",
    "թ": "t" + ASPIRATE, "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "dz", "կ": "g",
    "հ": "h", "ձ": "ts", "ղ": "gh", "ճ": "j", "մ": "m", "յ": "y", "ն": "n", "շ": "sh",
    "ո": "o", "չ": "ch" + ASPIRATE, "պ": "b", "ջ": "ch", "ռ": "rr", "ս": "s", "վ": "v",
    "տ": "d", "ր": "r", "ց": "ts" + ASPIRATE, "ւ": "v", "փ": "p" + ASPIRATE,
    "ք": "k" + ASPIRATE, "օ": "o", "ֆ": "f",
}

# Classical: like Eastern for consonants; ը→ə (or e), initial յ→h, initial ե→ye
_BGN_CLASSICAL: dict[str, str] = {
    "ա": "a", "բ": "b", "գ": "g", "դ": "d", "ե": "e", "զ": "z", "է": "ē", "ը": "ə",
    "թ": "t" + ASPIRATE, "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts", "կ": "k",
    "հ": "h", "ձ": "dz", "ղ": "gh", "ճ": "ch", "մ": "m", "յ": "y", "ն": "n", "շ": "sh",
    "ո": "o", "չ": "ch" + ASPIRATE, "պ": "p", "ջ": "j", "ռ": "rr", "ս": "s", "վ": "v",
    "տ": "t", "ր": "r", "ց": "ts" + ASPIRATE, "ւ": "w", "փ": "p" + ASPIRATE,
    "ք": "k" + ASPIRATE, "օ": "o", "ֆ": "f",
}


def _get_bgn_table(dialect: Dialect) -> dict[str, str]:
    if dialect == "western":
        return _BGN_WESTERN
    if dialect == "classical":
        return _BGN_CLASSICAL
    return _BGN_EASTERN


# ─── Digraphs (process before single letters) ─────────────────────────
# և: yev initially / after vowel; ev elsewhere. BGN/PCGN.
# ու: u (always)
# իւ: yoo (Western/Classical), iw in some Eastern
def _apply_digraphs_and_context(text: str, dialect: Dialect) -> str:
    """Convert digraphs and context-dependent letters. Input normalized, lowercased."""
    table = _get_bgn_table(dialect)
    # Vowels that trigger "yev" for և (BGN/PCGN)
    vowel_after = set("աեէըիոյօ")
    i = 0
    out = []
    n = len(text)
    while i < n:
        c = text[i]
        # և → yev / ev (Armenian և = U+0587 or sequence ե+ւ)
        if c == "ե" and i + 1 < n and text[i + 1] == "ւ":
            prev_is_vowel = (i > 0 and text[i - 1] in vowel_after) or i == 0
            out.append("yev" if prev_is_vowel else "ev")
            i += 2
            continue
        # ու → "ou" (Western) or "u" (Eastern/Classical). Classical/Western: before vowel → "v"
        if c == "ո" and i + 1 < n and text[i + 1] == "ւ":
            next_c = text[i + 2] if i + 2 < n else ""
            if next_c and next_c in vowel_after:
                # ւ before vowel = v sound (classical/traditional)
                out.append("v")
                i += 2
                continue
            if dialect == "western":
                out.append("ou")
            else:
                out.append("u")
            i += 2
            continue
        # իւ → yoo (WA/Classical), ev or iw for Eastern in some systems; we use yoo for all for consistency
        if c == "ի" and i + 1 < n and text[i + 1] == "ւ":
            out.append("yoo")
            i += 2
            continue
        # Coalesced յե or յէ → always "ye" (never "y"+"ye") so e.g. հայերէն → hayeren
        if c == "յ" and i + 1 < n and text[i + 1] in ("ե", "է"):
            out.append("ye")
            i += 2
            continue
        # Surname ending: եան at end of word → "ian"; եա at end of word → "ia"
        if c == "ե" and i + 1 < n and text[i + 1] == "ա":
            bounds = _get_armenian_word_bounds(text, i)
            if i + 2 < n and text[i + 2] == "ն" and bounds is not None and i + 3 >= bounds[1]:
                out.append("ian")
                i += 3
                continue
            if bounds is not None and i + 2 >= bounds[1]:
                out.append("ia")
                i += 2
                continue
            out.append("ea")
            i += 2
            continue
        # այ: 3-letter word → "ye" (so բայ→pye, հայ→hye); if յ is followed by ե/է, output only "a" so next iteration coalesces յե/յէ→ye
        if c == "ա" and i + 1 < n and text[i + 1] == "յ":
            if i + 2 < n and text[i + 2] in ("ե", "է"):
                out.append("a")
                i += 1
                continue
            bounds = _get_armenian_word_bounds(text, i)
            word_len = (bounds[1] - bounds[0]) if bounds else 0
            at_word_end = bounds is not None and i + 2 >= bounds[1]
            if word_len == 3:
                out.append("ye")  # so English speakers read like "pie", "high"
            elif at_word_end:
                out.append("a")
            else:
                out.append("ay")
            i += 2
            continue
        # եյ: "ey" between consonants; at end of word յ silent unless 3-letter word
        if c == "ե" and i + 1 < n and text[i + 1] == "յ":
            bounds = _get_armenian_word_bounds(text, i)
            word_len = (bounds[1] - bounds[0]) if bounds else 0
            at_word_end = bounds is not None and i + 2 >= bounds[1]
            if at_word_end and word_len != 3:
                out.append("e")
            else:
                out.append("ey")
            i += 2
            continue
        # ոյ: Western "uy" when not word-final or when 3-letter word (e.g. յոյս→huys); word-final "o" (silent յ) for longer words. IPA unchanged.
        if c == "ո" and i + 1 < n and text[i + 1] == "յ":
            bounds = _get_armenian_word_bounds(text, i)
            word_len = (bounds[1] - bounds[0]) if bounds else 0
            at_word_end = bounds is not None and i + 2 >= bounds[1]
            if at_word_end and word_len != 3:
                out.append("o")
            elif dialect == "western":
                out.append("uy")  # non-final or 3-letter word
            else:
                out.append("oy")
            i += 2
            continue
        # Single-letter context: ո, ե, յ
        if c == "ո":
            # vo initially (before consonant); o after consonant or end
            if i == 0 or (i > 0 and _is_armenian_vowel(text[i - 1])):
                next_c = text[i + 1] if i + 1 < n else ""
                if next_c and next_c not in "աեէըիոյօ":
                    out.append("vo")
                else:
                    out.append(table["ո"])
            else:
                out.append(table["ո"])
            i += 1
            continue
        if c == "ե":
            # Classical/Eastern: ye at start or after vowel; e elsewhere.
            # Western: ye only at word start; within words use plain e (di-e-zeragan, not di-ye-zeragan).
            if dialect == "western":
                if i == 0:
                    out.append("ye")
                else:
                    out.append(table["ե"])
            else:
                if i == 0 or (i > 0 and text[i - 1] in vowel_after):
                    out.append("ye")
                else:
                    out.append(table["ե"])
            i += 1
            continue
        if c == "յ":
            bounds = _get_armenian_word_bounds(text, i)
            word_len = (bounds[1] - bounds[0]) if bounds else 0
            at_word_end = bounds is not None and i + 1 >= bounds[1]
            if at_word_end and word_len != 3:
                # Word-final յ silent unless 3-letter word
                i += 1
                continue
            if dialect == "classical" and i == 0:
                out.append("h")
            elif dialect == "western" and i == 0:
                out.append("h")
            else:
                out.append(table["յ"])
            i += 1
            continue
        out.append(table.get(c, c))
        i += 1
    return "".join(out)


def to_latin(text: str, dialect: Dialect = "western", insert_schwa: bool = True) -> str:
    """
    Convert Armenian script to Latin (BGN/PCGN style) for the given dialect.

    - eastern: BGN/PCGN 1981 base (բ=b, պ=p, ջ=j, ճ=ch, etc.)
    - classical: Like Eastern with ə for ը, ē for է, initial յ→h, initial ե→ye
    - western: Voicing reversal (բ=p, պ=b, ճ=j, ջ=ch, ձ=ts, ծ=dz), ը→u, թ→t

    For Western, insert_schwa defaults to True: unwritten ը is inserted before word-initial
    ս+կ/պ/տ/ք and between two consonants (e.g. Ինքզինքս → ink'uzink'us). Set to False for spelling-only.
    """
    if not text:
        return ""
    text = _normalize_armenian(text)
    # Enforce Western Armenian orthography rules when requested: detect Eastern/reform
    # orthography markers and refuse to transliterate Western if any are present.
    if dialect == "western":
        # Lazy import to avoid heavy imports at module load time
        try:
            from hytools.linguistics.dialect import branch_dialect_classifier as _bdc
        except Exception:
            _bdc = None
        if _bdc is not None:
            ea_markers = [re.compile(p, flags=re.IGNORECASE) for p, _ in _bdc.get_eastern_markers()]
            detected = []
            for pat in ea_markers:
                if pat.search(text):
                    detected.append(pat.pattern)
            if detected:
                raise ValueError(
                    f"Input appears to contain Eastern/reform orthography markers not allowed for Western Armenian: {detected}"
                )
    if insert_schwa and dialect == "western":
        text = _insert_unwritten_schwa_western(text)
    latin = _apply_digraphs_and_context(text, dialect)
    # Western cleanup: avoid spurious double-y in sequences like "hayyeren" → "hayeren".
    if dialect == "western":
        latin = latin.replace("ayye", "aye")
    return latin


def format_wa_latin_sentence(latin_text: str, normalize_punctuation: bool = True, sentence_case: bool = True) -> str:
    """
    Format Western Armenian Latin output for readability: normalize punctuation (Armenian full stop ։ → .)
    and apply sentence-case (capitalize first letter of each sentence).

    Use after to_latin(..., "western") for display. Example:
      to_latin("Տունը մեծ է։ Ան կը խօսի հայերէն։", "western")  → "dounu medz e։ an gu khosi hayeren։"
      format_wa_latin_sentence(...)  → "Dounu medz e. An gu khosi hayeren."
    """
    if not latin_text:
        return ""
    s = latin_text
    if normalize_punctuation:
        s = s.replace("\u0589", ".")  # Armenian full stop → period
    if not sentence_case:
        return s
    # Capitalize first letter of the string and after sentence-ending punctuation (. ! ?)
    out: list[str] = []
    cap_next = True
    for i, c in enumerate(s):
        if cap_next and c.isalpha():
            out.append(c.upper())
            cap_next = False
        else:
            out.append(c)
            if c in ".!?" and (i + 1 >= len(s) or s[i + 1].isspace() or s[i + 1] in ".!?"):
                cap_next = True
    return "".join(out)


# ─── Reverse: Latin → Armenian ────────────────────────────────────────
# Build reverse maps per dialect. For digraphs we need longest-match (e.g. "yev" before "ye"+"v").
# Single roman → Armenian: many-to-one (ch→ճ or ջ in EA; in WA ch→ջ, j→ճ).

def _build_reverse_table(dialect: Dialect) -> dict[str, str]:
    """One roman string → one Armenian letter (for single-letter mapping)."""
    fwd = _get_bgn_table(dialect)
    rev: dict[str, str] = {}
    for arm, rom in fwd.items():
        # Prefer first occurrence when multiple map to same roman (e.g. թ and տ both t in WA)
        if rom not in rev:
            rev[rom] = arm
        # For aspirates we store with ʼ
    return rev


# Reverse digraphs and multi-char: longest first. For Western: ou/oo→ու, u→ը; for Eastern/Classical: u→ու.
# We include both vowel digraphs (yoo, yev, ev, vo, ye, ou, oo) and consonant clusters (zh, kh, sh, ch, dz, gh, rr, ts, etc.).
# Order matters: longer sequences first.
_BASE_REV_DIGRAPHS_EASTERN: list[tuple[str, str]] = [
    ("yoo", "իւ"), ("yev", "և"), ("ev", "և"), ("vo", "ո"), ("ye", "ե"),
]
_BASE_REV_DIGRAPHS_CLASSICAL: list[tuple[str, str]] = [
    ("yoo", "իւ"), ("yev", "և"), ("ev", "և"), ("vo", "ո"), ("ye", "ե"),
]
_BASE_REV_DIGRAPHS_WESTERN: list[tuple[str, str]] = [
    ("yoo", "իւ"), ("yev", "և"), ("ev", "և"), ("vo", "ո"), ("ye", "ե"), ("ou", "ու"), ("oo", "ու"), ("uy", "ոյ"),
]


def _build_consonant_multichar(fwd: dict[str, str], exclude: set[str]) -> list[tuple[str, str]]:
    """Build (roman, armenian) list for all multi-char roman sequences from a forward table."""
    pairs: list[tuple[str, str]] = []
    for arm, rom in fwd.items():
        if len(rom) > 1 and rom not in exclude:
            pairs.append((rom, arm))
    # Longest roman sequences first for greedy matching
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


_REV_DIGRAPHS_EASTERN: list[tuple[str, str]] = _BASE_REV_DIGRAPHS_EASTERN + _build_consonant_multichar(
    _BGN_EASTERN, exclude={"yoo", "yev", "ev", "vo", "ye"}
)
_REV_DIGRAPHS_CLASSICAL: list[tuple[str, str]] = _BASE_REV_DIGRAPHS_CLASSICAL + _build_consonant_multichar(
    _BGN_CLASSICAL, exclude={"yoo", "yev", "ev", "vo", "ye"}
)
# Western: "ou" and "oo" → ու; single "u" → ը (schwa)
# In Western Armenian, "և" is only used for the word "and"; "yev"/"ev" inside words → "եւ" (two chars).
_REV_DIGRAPHS_WESTERN: list[tuple[str, str]] = _BASE_REV_DIGRAPHS_WESTERN + _build_consonant_multichar(
    _BGN_WESTERN, exclude={"yoo", "yev", "ev", "vo", "ye", "ou", "oo"}
) + [("u", "ը")]
# Western: same sequences but we'll replace yev/ev with եւ when not standalone "and"
_WESTERN_AND_TOKENS = frozenset({"and", "ev", "yev"})


def _is_standalone_token(roman_text: str, start: int, length: int) -> bool:
    """True if the span [start:start+length] is a standalone token (word boundaries)."""
    n = len(roman_text)
    end = start + length
    before_ok = start == 0 or not roman_text[start - 1].isalpha()
    after_ok = end == n or not roman_text[end].isalpha()
    return before_ok and after_ok
_REV_EASTERN: dict[str, str] = _build_reverse_table("eastern")
_REV_CLASSICAL: dict[str, str] = _build_reverse_table("classical")
_REV_WESTERN: dict[str, str] = _build_reverse_table("western")


def _get_reverse_table(dialect: Dialect) -> dict[str, str]:
    if dialect == "western":
        return _REV_WESTERN
    if dialect == "classical":
        return _REV_CLASSICAL
    return _REV_EASTERN


def _get_reverse_digraphs(dialect: Dialect) -> list[tuple[str, str]]:
    if dialect == "western":
        return _REV_DIGRAPHS_WESTERN
    if dialect == "classical":
        return _REV_DIGRAPHS_CLASSICAL
    return _REV_DIGRAPHS_EASTERN


def to_armenian(roman_text: str, dialect: Dialect = "western") -> str:
    """
    Convert Latin (BGN/PCGN-style) romanization back to Armenian script.

    Ambiguities: multiple Latin sequences can map to one Armenian (e.g. "t" → թ or տ in EA).
    We use the dialect's canonical reverse map; for ambiguous cases the first match in the
    table wins. For best results use consistent romanization (e.g. with aspirate ʼ).
    """
    if not roman_text:
        return ""
    roman_text = roman_text.strip()
    # Accept both modifier letter apostrophe (U+02BC) and ASCII apostrophe for aspirates
    if "'" in roman_text:
        roman_text = roman_text.replace("'", ASPIRATE)
    table = _get_reverse_table(dialect)
    rev_digraphs = _get_reverse_digraphs(dialect)
    out = []
    i = 0
    n = len(roman_text)
    while i < n:
        matched = False
        # Western/Classical: "ian" at end of word (surname) → եան
        if dialect in ("western", "classical") and i + 3 <= n and roman_text[i:i + 3].lower() == "ian":
            end_ok = i + 3 == n or not roman_text[i + 3].isalpha()
            if end_ok:
                out.append("եան")
                i += 3
                matched = True
        # Western: standalone "and" → և
        if not matched and dialect == "western" and i + 3 <= n and roman_text[i:i + 3].lower() == "and" and _is_standalone_token(roman_text, i, 3):
            out.append("և")
            i += 3
            matched = True
        if not matched:
            for seq, arm in rev_digraphs:
                if roman_text[i:i + len(seq)].lower() == seq:
                    # Western: use եւ in words, և only for standalone "and"
                    if dialect == "western" and seq in ("yev", "ev"):
                        if _is_standalone_token(roman_text, i, len(seq)) and seq in _WESTERN_AND_TOKENS:
                            out.append("և")
                        else:
                            out.append("եւ")
                    else:
                        out.append(arm)
                    i += len(seq)
                    matched = True
                    break
        if matched:
            continue
        # Single char or aspirate
        if i + 1 < n and roman_text[i + 1] == ASPIRATE:
            two = roman_text[i:i + 2].lower()
            if two in ("tʼ", "chʼ", "tsʼ", "pʼ", "kʼ"):
                arm = {"tʼ": "թ", "chʼ": "չ", "tsʼ": "ց", "pʼ": "փ", "kʼ": "ք"}[two]
                out.append(arm)
                i += 2
                continue
        one = roman_text[i].lower()
        if one in table:
            out.append(table[one])
        else:
            out.append(roman_text[i])
        i += 1
    return "".join(out)


# ─── IPA (Armenian → IPA string) ─────────────────────────────────────
# Western: from WESTERN_ARMENIAN_PHONETICS_GUIDE.md / phonetics.py
# Eastern: reverse voicing + different IPA for some (e.g. ր tap, ղ different)
# Classical: similar to Eastern, with ə for ը, ɛ for է

_IPA_WESTERN: dict[str, str] = {
    "ա": "ɑ", "բ": "p", "գ": "k", "դ": "t", "ե": "ɛ", "զ": "z", "է": "ɛ", "ը": "ə",
    "թ": "t", "ժ": "ʒ", "ի": "i", "լ": "l", "խ": "x", "ծ": "dz", "կ": "g", "հ": "h",
    "ձ": "ts", "ղ": "ɣ", "ճ": "dʒ", "մ": "m", "յ": "j", "ն": "n", "շ": "ʃ", "ո": "ɔ",
    "չ": "tʃ", "պ": "b", "ջ": "tʃ", "ռ": "r", "ս": "s", "վ": "v", "տ": "d", "ր": "ɾ",
    "ց": "ts", "ւ": "v", "փ": "p", "ք": "k", "օ": "o", "ֆ": "f",
}

_IPA_EASTERN: dict[str, str] = {
    "ա": "ɑ", "բ": "b", "գ": "g", "դ": "d", "ե": "ɛ", "զ": "z", "է": "ɛ", "ը": "ə",
    "թ": "tʰ", "ժ": "ʒ", "ի": "i", "լ": "l", "խ": "χ", "ծ": "ts", "կ": "k", "հ": "h",
    "ձ": "dz", "ղ": "ʁ", "ճ": "tʃ", "մ": "m", "յ": "j", "ն": "n", "շ": "ʃ", "ո": "ɔ",
    "չ": "tʃʰ", "պ": "p", "ջ": "dʒ", "ռ": "r", "ս": "s", "վ": "v", "տ": "t", "ր": "ɾ",
    "ց": "tsʰ", "ւ": "v", "փ": "pʰ", "ք": "kʰ", "օ": "o", "ֆ": "f",
}

_IPA_CLASSICAL: dict[str, str] = {
    "ա": "ɑ", "բ": "b", "գ": "g", "դ": "d", "ե": "ɛ", "զ": "z", "է": "ɛ", "ը": "ə",
    "թ": "tʰ", "ժ": "ʒ", "ի": "i", "լ": "l", "խ": "χ", "ծ": "ts", "կ": "k", "հ": "h",
    "ձ": "dz", "ղ": "ʁ", "ճ": "tʃ", "մ": "m", "յ": "j", "ն": "n", "շ": "ʃ", "ո": "ɔ",
    "չ": "tʃʰ", "պ": "p", "ջ": "dʒ", "ռ": "r", "ս": "s", "վ": "v", "տ": "t", "ր": "ɾ",
    "ց": "tsʰ", "ւ": "v", "փ": "pʰ", "ք": "kʰ", "օ": "o", "ֆ": "f",
}


def _get_ipa_table(dialect: Dialect) -> dict[str, str]:
    if dialect == "western":
        return _IPA_WESTERN
    if dialect == "eastern":
        return _IPA_EASTERN
    return _IPA_CLASSICAL


# Diphthongs for IPA
_IPA_DIPHTHONGS = {"ու": "u", "իւ": "ju"}


def to_ipa(text: str, dialect: Dialect = "western", insert_schwa: bool = True) -> str:
    """
    Convert Armenian script to IPA string for the given dialect.

    Context: ե→jɛ word-init, ɛ elsewhere; ո→vo before consonant, ɔ elsewhere;
    յ→h word-init in Western/Classical, j elsewhere.

    For Western, insert_schwa defaults to True: unwritten ə is inserted before word-initial
    ս+կ/պ/տ/ք and between two consonants.
    """
    if not text:
        return ""
    text = _normalize_armenian(text)
    if insert_schwa and dialect == "western":
        text = _insert_unwritten_schwa_western(text)
    table = _get_ipa_table(dialect)
    out = []
    i = 0
    n = len(text)
    vowel_after = set("աեէըիոյօ")
    while i < n:
        # Digraphs
        if i + 1 < n:
            two = text[i] + text[i + 1]
            if two in _IPA_DIPHTHONGS:
                out.append(_IPA_DIPHTHONGS[two])
                i += 2
                continue
        c = text[i]
        if c == "ե":
            out.append("jɛ" if (i == 0 or (i > 0 and text[i - 1] in vowel_after)) else "ɛ")
        elif c == "ո":
            next_c = text[i + 1] if i + 1 < n else ""
            if next_c and next_c not in "աեէըիոյօ":
                out.append("vo")  # or ʋɔ
            else:
                out.append(table.get("ո", "ɔ"))
        elif c == "յ":
            # For IPA, mirror the Latin behavior: in Western/Classical, word-final յ
            # is typically silent except in 3-letter words (e.g. հայ). We approximate
            # this by dropping final յ when word length != 3.
            bounds = _get_armenian_word_bounds(text, i)
            word_len = (bounds[1] - bounds[0]) if bounds else 0
            at_word_end = bounds is not None and i + 1 >= bounds[1]
            if at_word_end and word_len != 3:
                i += 1
                continue
            out.append("h" if i == 0 else "j")
        else:
            out.append(table.get(c, c))
        i += 1
    return "".join(out)


# ─── Expose mappings for documentation/report ─────────────────────────
def get_armenian_to_latin_map(dialect: Dialect) -> dict[str, str]:
    """Return the full Armenian → Latin mapping used by to_latin (single letters + key digraphs/diphthongs).
    Note: եա is 'ea' in general but 'ia' at end of surname (e.g. -եան → -ian). Word-final յ in այ/եյ/ոյ is silent unless the word has 3 letters."""
    table = dict(_get_bgn_table(dialect))
    # Add canonical digraph/diphthong mappings for documentation/demo purposes.
    if dialect == "western":
        table["ու"] = "ou"
        table["իւ"] = "yoo"
        table["եա"] = "ea"  # "ia" at end of surname (to_latin applies this context)
        table["ոյ"] = "uy"  # non-final or 3-letter word; word-final (4+ letters) → "o" (silent յ)
        table["այ"] = "ay"
        table["եյ"] = "ey"
    else:
        table["ու"] = "u"
        table["իւ"] = "yoo"
        table["եա"] = "ea"
        table["ոյ"] = "oy"
        table["այ"] = "ay"
        table["եյ"] = "ey"
    return table


def get_latin_to_armenian_map(dialect: Dialect) -> dict[str, str]:
    """Return the Latin → Armenian reverse mapping used by to_armenian."""
    return dict(_get_reverse_table(dialect))


def get_armenian_to_ipa_map(dialect: Dialect) -> dict[str, str]:
    """Return the Armenian → IPA mapping used by to_ipa (letters + key digraphs/diphthongs)."""
    table = dict(_get_ipa_table(dialect))
    # Diphthongs (see WESTERN_ARMENIAN_PHONETICS_GUIDE and ARMENIAN_QUICK_REFERENCE)
    if dialect == "western":
        table["ու"] = _IPA_DIPHTHONGS["ու"]
        table["իւ"] = _IPA_DIPHTHONGS["իւ"]
        table["եա"] = "ɛɑ"
        table["ոյ"] = "uj"
        table["այ"] = "aj"
        table["եյ"] = "ɛj"
    else:
        table["ու"] = _IPA_DIPHTHONGS["ու"]
        table["իւ"] = _IPA_DIPHTHONGS["իւ"]
        table["եա"] = "ɛɑ"
        table["ոյ"] = "uj"
        table["այ"] = "aj"
        table["եյ"] = "ɛj"
    return table


__all__ = [
    "Dialect",
    "ASPIRATE",
    "to_latin",
    "to_armenian",
    "to_ipa",
    "format_wa_latin_sentence",
    "get_armenian_to_latin_map",
    "get_latin_to_armenian_map",
    "get_armenian_to_ipa_map",
]
