"""Tesseract configuration constants and helpers for Armenian OCR."""

from __future__ import annotations

# Primary language string passed to Tesseract.
# Tesseract has no separate Western Armenian (hyw) or Classical (hyc) model;
# `hye` covers the shared Armenian script for all varieties.
#
# Language selection (see FUTURE_IMPROVEMENTS.md for per-page detection):
#   hye       — Armenian-only pages (best accuracy, fewer eng misreads)
#   hye+eng   — Mixed Armenian + English (default for unknown/mixed)
#   eng       — English-only pages
TESSERACT_LANG = "hye+eng"

# Per-page language config keys (used when per_page_lang is "auto" or when overriding)
TESSERACT_LANG_ARMENIAN = "hye"
TESSERACT_LANG_MIXED = "hye+eng"
TESSERACT_LANG_ENGLISH = "eng"

# Page segmentation mode: 3 = fully automatic, 6 = assume uniform block of text
PSM_AUTO = 3
PSM_BLOCK = 6

# OEM: 3 = default (LSTM); 1 = LSTM only (recommended for hye)
OEM_LSTM = 1

# Tesseract config string used by pytesseract
def build_config(psm: int = PSM_AUTO, oem: int = OEM_LSTM, extra: str = "") -> str:
    """Return a Tesseract config string.

    Example::

        build_config(psm=6) → "--psm 6 --oem 1"
    """
    cfg = f"--psm {psm} --oem {oem}"
    if extra:
        cfg += f" {extra}"
    return cfg


# Armenian Unicode ranges used for script detection
ARMENIAN_RANGE_START = 0x0530
ARMENIAN_RANGE_END = 0x058F

# Armenian ligature code points (U+FB13–U+FB17)
ARMENIAN_LIGATURES: dict[str, str] = {
    "\uFB13": "\u0574\u0576",  # մն
    "\uFB14": "\u0574\u0565",  # մե
    "\uFB15": "\u0574\u056B",  # մի
    "\uFB16": "\u057E\u0576",  # վն
    "\uFB17": "\u0574\u056D",  # մխ
}


def script_ratio_from_text(text: str) -> tuple[float, float]:
    """Compute Armenian and Latin character ratios in text (by code point count).

    Returns
    -------
    (armenian_ratio, latin_ratio)
        Each in [0, 1]; armenian_ratio + latin_ratio <= 1 (other scripts ignored).
    """
    armenian = 0
    latin = 0
    for c in text:
        cp = ord(c)
        if ARMENIAN_RANGE_START <= cp <= ARMENIAN_RANGE_END:
            armenian += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            latin += 1
    total = armenian + latin
    if total == 0:
        return 0.0, 0.0
    return armenian / total, latin / total


def choose_tesseract_lang_from_ratio(
    armenian_ratio: float,
    latin_ratio: float,
    armenian_only_threshold: float = 0.9,
    english_only_threshold: float = 0.9,
    lang_armenian: str = TESSERACT_LANG_ARMENIAN,
    lang_mixed: str = TESSERACT_LANG_MIXED,
    lang_english: str = TESSERACT_LANG_ENGLISH,
) -> str:
    """Choose Tesseract language string from script ratios.

    If Armenian ratio >= armenian_only_threshold → lang_armenian (e.g. hye).
    If Latin ratio >= english_only_threshold → lang_english (e.g. eng).
    Otherwise → lang_mixed (e.g. hye+eng).
    """
    # Strict thresholds first (backwards-compatible behavior)
    if armenian_ratio >= armenian_only_threshold:
        return lang_armenian
    if latin_ratio >= english_only_threshold:
        return lang_english

    # When neither script dominates by the strict threshold, prefer a
    # language if its ratio notably exceeds the other and exceeds a
    # modest minimum. This makes auto-detection more permissive for
    # English when Armenian characters appear spuriously in mixed-mode
    # probe output.
    MIN_SCRIPT_THRESHOLD = 0.35
    if latin_ratio > armenian_ratio and latin_ratio >= MIN_SCRIPT_THRESHOLD:
        return lang_english
    if armenian_ratio > latin_ratio and armenian_ratio >= MIN_SCRIPT_THRESHOLD:
        return lang_armenian

    # Fall back to mixed when ambiguous
    return lang_mixed
