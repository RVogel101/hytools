"""Post-processing for raw Tesseract OCR output on Armenian text.

Handles:
- Armenian ligature decomposition (U+FB13–U+FB17)
- Unicode NFC normalization
- Armenian punctuation normalization
- Removal of low-confidence / garbage lines
- Spell-check stub (word-list based)
"""

from __future__ import annotations

import re
import unicodedata

from .tesseract_config import ARMENIAN_LIGATURES

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
    """Drop lines where the ratio of Armenian characters is below *min_armenian_ratio*.

    This filters out lines that are mostly OCR noise.
    """
    clean_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue
        armenian_chars = sum(
            1 for c in stripped if "\u0530" <= c <= "\u058F"
        )
        ratio = armenian_chars / len(stripped)
        if ratio >= min_armenian_ratio or len(stripped) < 5:
            clean_lines.append(line)
        # else: silently drop high-noise lines
    return "\n".join(clean_lines)


def postprocess(
    raw_text: str,
    min_armenian_ratio: float = 0.3,
) -> str:
    """Apply the full post-processing pipeline to raw Tesseract output.

    Parameters
    ----------
    raw_text:
        The raw string returned by ``pytesseract.image_to_string``.
    min_armenian_ratio:
        Minimum fraction of Armenian characters required for a line to be kept.

    Returns
    -------
    str
        Cleaned, normalized text.
    """
    text = decompose_ligatures(raw_text)
    text = normalize_unicode(text)
    text = normalize_punctuation(text)
    text = remove_garbage_lines(text, min_armenian_ratio=min_armenian_ratio)
    return text.strip()
