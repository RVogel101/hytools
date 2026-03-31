"""Priority A: extract text from PDF text layer when glyphs are embedded (no OCR).

Skips raster OCR for pages that already have selectable text — critical for
multi-column vector layouts where global Tesseract fails.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Armenian + Latin letters for quality heuristic
_ARM_RE = re.compile(r"[\u0530-\u058F\uFB13-\uFB17]")
_LAT_RE = re.compile(r"[A-Za-z]")


def _has_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def extract_page_text_pymupdf(pdf_path: Path, page_num: int) -> str | None:
    """Extract UTF-8 text for one page using PyMuPDF (1-based page index).

    Returns None if PyMuPDF is not installed or extraction fails.
    """
    if not _has_pymupdf():
        return None
    import fitz

    path = Path(pdf_path)
    if not path.is_file():
        return None
    try:
        doc = fitz.open(path)
        try:
            if page_num < 1 or page_num > len(doc):
                return None
            page = doc[page_num - 1]
            return page.get_text("text") or ""
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("PyMuPDF extract failed for %s p%d: %s", path.name, page_num, exc)
        return None


def is_acceptable_text_layer(
    text: str,
    min_chars: int = 40,
    min_script_ratio: float = 0.15,
) -> bool:
    """Return True if extracted text looks like real content, not junk/empty."""
    s = (text or "").strip()
    if len(s) < min_chars:
        return False
    letters = len(_ARM_RE.findall(s)) + len(_LAT_RE.findall(s))
    ratio = letters / max(len(s), 1)
    if ratio < min_script_ratio:
        return False
    # Reject mostly replacement chars / control noise
    bad = sum(1 for c in s if ord(c) < 32 and c not in "\n\t\r")
    if bad / max(len(s), 1) > 0.05:
        return False
    return True


def try_text_layer_page(pdf_path: Path, page_num: int, **kwargs: Any) -> str | None:
    """Extract page text; return string if acceptable, else None."""
    raw = extract_page_text_pymupdf(pdf_path, page_num)
    if raw is None:
        return None
    if not is_acceptable_text_layer(raw, **kwargs):
        logger.debug("Text layer for page %d rejected by heuristic (len=%d)", page_num, len(raw.strip()))
        return None
    logger.info("Using PDF text layer for %s page %d (%d chars)", pdf_path.name, page_num, len(raw.strip()))
    return raw
