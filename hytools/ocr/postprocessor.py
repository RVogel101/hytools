"""Post-processing for raw Tesseract OCR output on Armenian text.

Handles:
- Armenian ligature decomposition (U+FB13–U+FB17)
- Unicode NFC normalization
- Armenian punctuation normalization
- Armenian OCR confusion-pair correction (validated against Nayiri)
- Removal of low-confidence / garbage lines
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

from .tesseract_config import ARMENIAN_LIGATURES

logger = logging.getLogger(__name__)

# ── Armenian OCR confusion pairs ─────────────────────────────────────────────
# Each tuple is (wrong_char, correct_char).  Tesseract commonly confuses these
# Armenian glyphs.  Corrections are applied only when the replacement produces
# a word present in the Nayiri word-list.
_CONFUSION_PAIRS: list[tuple[str, str]] = [
    ("\u0573", "\u0570"),  # ճ → հ
    ("\u0576", "\u0562"),  # ն → բ
    (",", "\u0579"),       # , → չ  (ASCII comma misread as չ)
    ("\u054A", "\u0570"),  # Պ → հ
]

# Armenian Unicode range for token detection.
_ARMENIAN_RE = re.compile(r"[\u0530-\u058F]")

# Simple whitespace tokeniser that preserves inter-token spacing.
_TOKEN_SPLIT_RE = re.compile(r"(\S+)")

# Armenian-specific punctuation that should be preserved
_ARMENIAN_PUNCT = {
    "\u055D",  # ՝ Armenian comma
    "\u055E",  # ՞ Armenian question mark
    "\u0589",  # ։ Armenian full stop
    "\u055B",  # ՛ Armenian emphasis mark
    "\u055C",  # ՜ Armenian exclamation mark
}

# Pattern matching runs of non-Armenian, non-Latin, non-space characters
# that are likely OCR garbage on an Armenian page.
_GARBAGE_RE = re.compile(r"[^\u0530-\u058F\u0020-\u007E\s]{4,}")


def decompose_ligatures(text: str) -> str:
    """Replace Armenian ligature code points with their component characters."""
    for ligature, components in ARMENIAN_LIGATURES.items():
        text = text.replace(ligature, components)
    return text


def normalize_unicode(text: str) -> str:
    """Normalize *text* to NFC Unicode form."""
    return unicodedata.normalize("NFC", text)


def normalize_punctuation(text: str) -> str:
    """Replace common Western punctuation look-alikes with Armenian equivalents.

    For example, a plain ``?`` at the end of an Armenian sentence is often
    the result of OCR misreading the Armenian question mark ``՞``.  We leave
    this heuristic conservative to avoid over-correcting mixed-language text.
    """
    # Replace double-dot "period" sequences that Tesseract sometimes emits
    # instead of the Armenian full stop ։ (U+0589).
    text = re.sub(r"(?<=\S)\.\.", "։", text)
    return text


def remove_garbage_lines(text: str, min_armenian_ratio: float = 0.3) -> str:
    """Drop lines that are mostly OCR noise.

    A line is kept when:
    - it is blank or very short (< 5 chars),
    - its Armenian ratio meets *min_armenian_ratio*, **or**
    - it is predominantly Latin/English (Latin ratio ≥ 0.6) – common in
      bilingual textbooks.
    """
    clean_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue
        if len(stripped) < 5:
            clean_lines.append(line)
            continue
        armenian_chars = sum(
            1 for c in stripped if "\u0530" <= c <= "\u058F"
        )
        latin_chars = sum(
            1 for c in stripped if "A" <= c <= "Z" or "a" <= c <= "z"
        )
        total = len(stripped)
        arm_ratio = armenian_chars / total
        latin_ratio = latin_chars / total
        if arm_ratio >= min_armenian_ratio or latin_ratio >= 0.6:
            clean_lines.append(line)
        # else: silently drop high-noise lines
    return "\n".join(clean_lines)


# ── Confusion-pair correction ────────────────────────────────────────────────

def _is_armenian_token(token: str) -> bool:
    """Return *True* when *token* contains at least one Armenian character."""
    return bool(_ARMENIAN_RE.search(token))


def _generate_candidates(token: str) -> list[str]:
    """Generate candidate corrections for *token* by applying confusion pairs.

    Only single-character substitutions are tried (one pair per candidate).
    """
    candidates: list[str] = []
    for wrong, correct in _CONFUSION_PAIRS:
        if wrong in token:
            candidates.append(token.replace(wrong, correct, 1))
        if correct in token:
            candidates.append(token.replace(correct, wrong, 1))
    return candidates


def apply_confusion_corrections(
    text: str,
    wordset: Optional[set[str]] = None,
) -> str:
    """Replace OCR-confused characters when the corrected word is in *wordset*.

    If *wordset* is ``None`` or empty, the text is returned unchanged.  Only
    Armenian tokens are evaluated; English/Latin tokens pass through untouched.
    A substitution is accepted only when **exactly one** candidate matches the
    word-list (ambiguous cases are left alone).
    """
    if not wordset:
        return text

    from .nayiri_spellcheck import is_valid_word

    parts = _TOKEN_SPLIT_RE.split(text)  # odd indices are tokens
    for i in range(1, len(parts), 2):
        token = parts[i]
        if not _is_armenian_token(token):
            continue
        if is_valid_word(token, wordset):
            continue  # already correct
        candidates = _generate_candidates(token)
        valid = [c for c in candidates if is_valid_word(c, wordset)]
        if len(valid) == 1:
            logger.debug("Confusion fix: %r → %r", token, valid[0])
            parts[i] = valid[0]
    return "".join(parts)


def postprocess(
    raw_text: str,
    min_armenian_ratio: float = 0.3,
    wordset: Optional[set[str]] = None,
) -> str:
    """Apply the full post-processing pipeline to raw Tesseract output.

    Parameters
    ----------
    raw_text:
        The raw string returned by ``pytesseract.image_to_string``.
    min_armenian_ratio:
        Minimum fraction of Armenian characters required for a line to be kept.
    wordset:
        Optional Nayiri word-form set.  When provided, OCR confusion-pair
        correction is applied after normalization.

    Returns
    -------
    str
        Cleaned, normalized text.
    """
    text = decompose_ligatures(raw_text)
    text = normalize_unicode(text)
    text = normalize_punctuation(text)
    text = apply_confusion_corrections(text, wordset=wordset)
    text = remove_garbage_lines(text, min_armenian_ratio=min_armenian_ratio)
    return text.strip()
