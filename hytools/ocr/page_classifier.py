"""Pre-OCR page classifier.

Analyses a rasterized page image *before* the main OCR pass and assigns it
one of the following categories, each of which implies an optimal Tesseract
strategy:

    pure_armenian — mostly Armenian script  → ``hye``, ``psm=6``
    mixed         — Armenian + English      → ``hye+eng``, ``psm=6``, zone OCR
    english       — mostly English/Latin    → ``eng``, ``psm=6``
    dictionary    — dense multi-column text → ``hye+eng``, ``psm=1``, column split
    table         — grid/tabular layout     → layout fallback, vector tables
    non_text      — blank or image-only     → skip / low confidence stub

Classification is intentionally cheap: it uses ink density, projection
profiles, and horizontal line detection on the binarized image, plus at
most one quick Tesseract probe for script-ratio estimation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from PIL import Image

from .preprocessor import BinarizationMethod, preprocess
from .tesseract_config import (
    TESSERACT_LANG_ARMENIAN,
    TESSERACT_LANG_ENGLISH,
    TESSERACT_LANG_MIXED,
    build_config,
    script_ratio_from_text,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Page categories
# ---------------------------------------------------------------------------

class PageType(str, Enum):
    PURE_ARMENIAN = "pure_armenian"
    MIXED = "mixed"
    ENGLISH = "english"
    DICTIONARY = "dictionary"
    TABLE = "table"
    NON_TEXT = "non_text"


# ---------------------------------------------------------------------------
#  Strategy dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageStrategy:
    """Recommended OCR strategy for a classified page."""
    page_type: PageType
    lang: str
    psm: int
    layout_fallback: bool
    try_vector_tables: bool
    zone_ocr: bool
    # Informational — not enforcement.  Pipeline can override.
    confidence: float  # 0–1 how sure the classifier is


# Prebuilt strategies
_STRATEGIES: dict[PageType, PageStrategy] = {
    PageType.PURE_ARMENIAN: PageStrategy(
        page_type=PageType.PURE_ARMENIAN,
        lang=TESSERACT_LANG_ARMENIAN,
        psm=6,
        layout_fallback=False,
        try_vector_tables=False,
        zone_ocr=False,
        confidence=0.0,
    ),
    PageType.MIXED: PageStrategy(
        page_type=PageType.MIXED,
        lang=TESSERACT_LANG_MIXED,
        psm=6,
        layout_fallback=False,
        try_vector_tables=False,
        zone_ocr=True,
        confidence=0.0,
    ),
    PageType.ENGLISH: PageStrategy(
        page_type=PageType.ENGLISH,
        lang=TESSERACT_LANG_ENGLISH,
        psm=6,
        layout_fallback=False,
        try_vector_tables=False,
        zone_ocr=False,
        confidence=0.0,
    ),
    PageType.DICTIONARY: PageStrategy(
        page_type=PageType.DICTIONARY,
        lang=TESSERACT_LANG_MIXED,
        psm=1,  # auto-segmentation works best for dense columns
        layout_fallback=True,
        try_vector_tables=False,
        zone_ocr=False,
        confidence=0.0,
    ),
    PageType.TABLE: PageStrategy(
        page_type=PageType.TABLE,
        lang=TESSERACT_LANG_MIXED,
        psm=6,
        layout_fallback=True,
        try_vector_tables=True,
        zone_ocr=False,
        confidence=0.0,
    ),
    PageType.NON_TEXT: PageStrategy(
        page_type=PageType.NON_TEXT,
        lang=TESSERACT_LANG_MIXED,
        psm=3,
        layout_fallback=False,
        try_vector_tables=False,
        zone_ocr=False,
        confidence=0.0,
    ),
}


# ---------------------------------------------------------------------------
#  Image-level feature extraction (cheap, no OCR)
# ---------------------------------------------------------------------------

def _pil_to_gray(img: Image.Image) -> np.ndarray:
    if img.mode != "L":
        img = img.convert("L")
    return np.asarray(img, dtype=np.uint8)


def ink_density(binary: np.ndarray) -> float:
    """Fraction of dark pixels (value 0) in a binary image."""
    return float(np.count_nonzero(binary == 0)) / max(binary.size, 1)


def count_vertical_valleys(
    gray: np.ndarray,
    min_col_width_px: int = 40,
    valley_fraction: float = 0.28,
) -> int:
    """Count vertical projection valleys — a proxy for the number of columns."""
    h, w = gray.shape[:2]
    if w < 2 * min_col_width_px:
        return 1
    ink = (gray < 200).astype(np.float32)
    proj = ink.sum(axis=0)
    if proj.max() <= 0:
        return 1
    pnorm = proj / (proj.max() + 1e-6)
    splits = 0
    for x in range(2, w - 2):
        if (pnorm[x] < valley_fraction
                and pnorm[x] <= pnorm[x - 1]
                and pnorm[x] <= pnorm[x + 1]):
            splits += 1
    return splits + 1  # regions = splits + 1


def count_horizontal_rules(
    binary: np.ndarray,
    min_length_fraction: float = 0.3,
) -> int:
    """Detect long horizontal lines — a table indicator.

    Uses a morphological horizontal kernel to find lines spanning at least
    *min_length_fraction* of the image width.
    """
    h, w = binary.shape[:2]
    kernel_len = max(30, int(w * min_length_fraction))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
    # binary is 0=ink 255=bg; invert so ink=255
    inv = cv2.bitwise_not(binary)
    detected = cv2.morphologyEx(inv, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len(contours)


def word_line_stats(
    binary: np.ndarray,
) -> tuple[int, float]:
    """Estimate line count and mean words-per-line from horizontal projection.

    Returns (line_count, mean_words_per_line_estimate).
    """
    h, w = binary.shape[:2]
    ink = (binary == 0).astype(np.float32)
    row_proj = ink.sum(axis=1)
    # Threshold: at least 1% of width
    threshold = w * 0.01
    in_line = False
    line_count = 0
    line_widths: list[float] = []
    line_start = 0

    for y in range(h):
        if row_proj[y] > threshold:
            if not in_line:
                in_line = True
                line_start = y
        else:
            if in_line:
                in_line = False
                line_count += 1
                # Estimate "width" of ink in this line for word-density proxy
                line_slice = ink[line_start:y, :]
                col_proj = line_slice.sum(axis=0)
                # Count runs of ink in the column projection
                runs = 0
                in_run = False
                for x in range(w):
                    if col_proj[x] > 0:
                        if not in_run:
                            in_run = True
                            runs += 1
                    else:
                        in_run = False
                line_widths.append(runs)

    if in_line:
        line_count += 1

    mean_wpline = sum(line_widths) / len(line_widths) if line_widths else 0.0
    return line_count, mean_wpline


# ---------------------------------------------------------------------------
#  Main classifier
# ---------------------------------------------------------------------------

def classify_page(
    pil_image: Image.Image,
    binarization: str = "sauvola",
    *,
    ink_threshold_low: float = 0.005,
    ink_threshold_high: float = 0.35,
    column_threshold: int = 3,
    hrule_threshold: int = 4,
    dictionary_min_lines: int = 30,
    dictionary_min_wpline: float = 3.0,
    script_probe: bool = True,
    armenian_threshold: float = 0.85,
    english_threshold: float = 0.85,
) -> PageStrategy:
    """Classify a page image and return the recommended OCR strategy.

    Parameters
    ----------
    pil_image:
        Rasterized page (PIL Image).
    binarization:
        Binarization method for preprocessing.
    ink_threshold_low:
        Ink density below this → NON_TEXT.
    ink_threshold_high:
        Ink density above this → likely scan artifact; fall through to probe.
    column_threshold:
        Number of vertical valleys ≥ this means multi-column (dictionary/table).
    hrule_threshold:
        Number of horizontal rules ≥ this → TABLE.
    dictionary_min_lines:
        Minimum line count to qualify as dictionary page.
    dictionary_min_wpline:
        Minimum mean words-per-line to qualify as dictionary.
    script_probe:
        Run a quick Tesseract probe for script ratio classification.
    armenian_threshold:
        Armenian ratio ≥ this → PURE_ARMENIAN (when script_probe is True).
    english_threshold:
        Latin ratio ≥ this → ENGLISH (when script_probe is True).
    """
    method = BinarizationMethod(binarization)
    preprocessed = preprocess(pil_image, method=method)
    gray = _pil_to_gray(preprocessed)
    # Binarize for feature extraction (Otsu for simplicity)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # ── Feature extraction ────────────────────────────────────────────────
    density = ink_density(binary)
    n_cols = count_vertical_valleys(gray)
    n_hrules = count_horizontal_rules(binary)
    n_lines, mean_wpl = word_line_stats(binary)

    logger.debug(
        "Classifier features: ink=%.4f cols=%d hrules=%d lines=%d wpl=%.1f",
        density, n_cols, n_hrules, n_lines, mean_wpl,
    )

    # ── Decision tree ─────────────────────────────────────────────────────

    # 1. Very low ink density → non-text / blank page
    if density < ink_threshold_low:
        return _strategy(PageType.NON_TEXT, confidence=0.9)

    # 2. Many horizontal rules → table
    if n_hrules >= hrule_threshold:
        return _strategy(PageType.TABLE, confidence=0.8)

    # 3. Multi-column layout
    if n_cols >= column_threshold:
        # Dictionary: many short lines with several words each
        if n_lines >= dictionary_min_lines and mean_wpl >= dictionary_min_wpline:
            return _strategy(PageType.DICTIONARY, confidence=0.7)
        # Otherwise: table-like (column layout without dense lines)
        return _strategy(PageType.TABLE, confidence=0.6)

    # 4. Script-ratio probe (requires Tesseract)
    if script_probe:
        try:
            ar_ratio, lat_ratio = _quick_script_probe(preprocessed)
            logger.debug("Script probe: ar=%.2f lat=%.2f", ar_ratio, lat_ratio)

            if ar_ratio >= armenian_threshold:
                return _strategy(PageType.PURE_ARMENIAN, confidence=0.8)
            if lat_ratio >= english_threshold:
                return _strategy(PageType.ENGLISH, confidence=0.8)
            if ar_ratio > 0 and lat_ratio > 0:
                return _strategy(PageType.MIXED, confidence=0.7)
            # Both zero → non-text (OCR returned nothing recognizable)
            if ar_ratio == 0 and lat_ratio == 0:
                return _strategy(PageType.NON_TEXT, confidence=0.5)
        except Exception as exc:
            logger.debug("Script probe failed: %s", exc)

    # 5. Fallback: enough ink to be text, default to mixed
    return _strategy(PageType.MIXED, confidence=0.4)


def _strategy(page_type: PageType, confidence: float) -> PageStrategy:
    """Return a prebuilt strategy with the given confidence."""
    base = _STRATEGIES[page_type]
    return PageStrategy(
        page_type=base.page_type,
        lang=base.lang,
        psm=base.psm,
        layout_fallback=base.layout_fallback,
        try_vector_tables=base.try_vector_tables,
        zone_ocr=base.zone_ocr,
        confidence=confidence,
    )


def _quick_script_probe(preprocessed_image) -> tuple[float, float]:
    """Run a lightweight Tesseract pass to estimate script ratios."""
    from ._tesseract_lazy import get_pytesseract

    pt = get_pytesseract()
    cfg = build_config(psm=6)
    text = pt.image_to_string(preprocessed_image, lang=TESSERACT_LANG_MIXED, config=cfg)
    return script_ratio_from_text(text)
