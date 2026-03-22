"""Armenian text tokenizer for frequency analysis.

Provides a consistent tokenization pipeline used across all scraping
sources for building the WA frequency corpus:

1. NFC Unicode normalization
2. Armenian ligature decomposition (U+FB13–U+FB17)
3. Armenian uppercase → lowercase conversion
4. Word extraction via Armenian-script regex
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Armenian ligature decomposition mapping (Unicode FB13–FB17)
_LIGATURE_MAP: dict[str, str] = {
    "\uFB13": "\u0574\u0576",  # ﬓ → մն
    "\uFB14": "\u0574\u0565",  # ﬔ → մե
    "\uFB15": "\u0574\u056B",  # ﬕ → մի
    "\uFB16": "\u057E\u0576",  # ﬖ → վն
    "\uFB17": "\u0574\u056D",  # ﬗ → մխ
}

# Regex for extracting contiguous Armenian-script words.
# Includes both upper (U+0531–U+0556) and lower (U+0561–U+0587) ranges
# plus the ligature block (U+FB13–U+FB17).
_ARMENIAN_WORD_RE = re.compile(r"[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+")

# Minimum word length (in characters) to include in frequency counts.
MIN_WORD_LENGTH = 2


def decompose_ligatures(text: str) -> str:
    """Replace Armenian presentation-form ligatures with their components."""
    for lig, decomposed in _LIGATURE_MAP.items():
        text = text.replace(lig, decomposed)
    return text


def armenian_lowercase(text: str) -> str:
    """Convert Armenian uppercase letters (U+0531–U+0556) to lowercase.

    Armenian lowercase is a simple offset: uppercase + 0x30 = lowercase.
    Non-Armenian characters are left unchanged.
    """
    chars = []
    for c in text:
        cp = ord(c)
        if 0x0531 <= cp <= 0x0556:
            chars.append(chr(cp + 0x30))
        else:
            chars.append(c)
    return "".join(chars)


def normalize(text: str) -> str:
    """Apply the full normalization pipeline (NFC → ligatures → lowercase)."""
    text = unicodedata.normalize("NFC", text)
    text = decompose_ligatures(text)
    text = armenian_lowercase(text)
    return text


def extract_words(text: str, min_length: int = MIN_WORD_LENGTH) -> list[str]:
    """Normalize *text* and extract Armenian words.

    Returns a list of lowercase Armenian word tokens (with ligatures
    decomposed) of at least *min_length* characters.
    """
    text = normalize(text)
    words = _ARMENIAN_WORD_RE.findall(text)
    if min_length > 1:
        words = [w for w in words if len(w) >= min_length]
    return words


def word_frequencies(text: str, min_length: int = MIN_WORD_LENGTH) -> Counter:
    """Return a Counter of Armenian word frequencies in *text*."""
    return Counter(extract_words(text, min_length))


def file_frequencies(path, min_length: int = MIN_WORD_LENGTH) -> Counter:
    """Return word frequencies for a single text file."""
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8")
    return word_frequencies(text, min_length)
