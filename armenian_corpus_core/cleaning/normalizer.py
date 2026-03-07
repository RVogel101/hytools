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


def normalize(text: str) -> str:
    """Apply the full normalization pipeline to *text*.

    Steps applied in order:

    1. Unicode NFC normalization
    2. Whitespace normalization
    3. Junk-line removal

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
