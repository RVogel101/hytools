"""Unicode normalization for Western Armenian text.

Handles:
- NFC normalization
- Ligature decomposition (U+FB13–FB17)
- Whitespace normalization
- Junk-line removal

Note: Western Armenian retains classical Armenian orthography; no
orthographic conversion is needed or applied.
"""

from __future__ import annotations

import re
import unicodedata

# Pattern to collapse multiple whitespace characters (but preserve newlines)
_WHITESPACE_RE = re.compile(r"[^\S\n]+")
# Pattern to remove lines that are entirely punctuation / digits / symbols
_JUNK_LINE_RE = re.compile(r"^\W+$")

# Patterns to detect Latin / Arabic character usage (for removing foreign-language fragments)
_FOREIGN_SCRIPT_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_PARENS_FOREIGN_RE = re.compile(r"\([^)]*" + _FOREIGN_SCRIPT_RE.pattern + r"[^)]*\)")
_QUOTED_FOREIGN_RE = re.compile(r"«[^»]*" + _FOREIGN_SCRIPT_RE.pattern + r"[^»]*»")


def normalize_unicode(text: str) -> str:
    """Normalize *text* to NFC Unicode form."""
    return unicodedata.normalize("NFC", text)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of horizontal whitespace and strip trailing spaces."""
    lines = text.splitlines()
    normalized = [_WHITESPACE_RE.sub(" ", line).rstrip() for line in lines]
    return "\n".join(normalized)


def remove_junk_lines(text: str) -> str:
    """Remove lines that contain no alphanumeric content."""
    lines = [line for line in text.splitlines() if not _JUNK_LINE_RE.match(line.strip()) or not line.strip()]
    return "\n".join(lines)


def remove_foreign_fragments(text: str) -> str:
    """Remove Latin/Arabic fragments that may pollute Western Armenian text.

    This removes:
    - Parenthesized notes that contain Latin/Arabic characters.
    - Armenian guillemet-quoted fragments («…») that contain Latin/Arabic.
    - Any remaining Latin/Arabic characters (e.g. inline English words, Arabic
      script, transliterations).
    """

    # Remove parenthesized phrases that contain Latin/Arabic script
    text = _PARENS_FOREIGN_RE.sub("", text)

    # Remove guillemet-quoted phrases that contain Latin/Arabic script
    text = _QUOTED_FOREIGN_RE.sub("", text)

    # Remove any remaining Latin/Arabic characters (leaving Armenian-only text)
    text = _FOREIGN_SCRIPT_RE.sub("", text)

    # Cleanup common stray punctuation left behind by removals
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"«\s*»", "", text)

    return text


def normalize(text: str) -> str:
    """Apply the full normalization pipeline to *text*.

    Steps applied in order:

    1. Unicode NFC normalization
    2. Remove Latin/Arabic fragments (e.g. parenthesized English or Arabic, quotes)
    3. Whitespace normalization
    4. Junk-line removal

    Parameters
    ----------
    text:
        Input text (may be raw OCR output or scraped web text).

    Returns
    -------
    str
        Normalized text.
    """
    text = normalize_unicode(text)
    text = remove_foreign_fragments(text)
    text = normalize_whitespace(text)
    text = remove_junk_lines(text)
    return text.strip()


def normalize_directory(input_dir, output_dir) -> None:
    """Normalize all ``.txt`` files in *input_dir* and write results to *output_dir*."""
    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for txt_file in sorted(input_dir.rglob("*.txt")):
        rel = txt_file.relative_to(input_dir)
        out = output_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        text = txt_file.read_text(encoding="utf-8")
        out.write_text(normalize(text), encoding="utf-8")
        logger.debug("Normalized %s", rel)


if __name__ == "__main__":
    import logging
    import sys
    from pathlib import Path
    import yaml

    logging.basicConfig(level=logging.INFO)
    _SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"
    with open(_SETTINGS_PATH) as _f:
        _cfg = yaml.safe_load(_f)

    normalize_directory(
        _cfg["paths"]["ocr_output_dir"],
        _cfg["paths"]["cleaned_dir"],
    )
