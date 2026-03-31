"""Priorities B–D: column splits, sparse PSM modes, reading-order assembly.

Used when full-page OCR collapses multi-column or sparse layouts.
"""

from __future__ import annotations

import logging
import numpy as np
import pytesseract
from PIL import Image

from hytools.ocr.postprocessor import postprocess
from hytools.ocr.preprocessor import BinarizationMethod, preprocess
from hytools.ocr.tesseract_config import build_config, script_ratio_from_text

logger = logging.getLogger(__name__)

# Tesseract PSM: 6 block, 11 sparse, 12 sparse + OSD
PSM_BLOCK = 6
PSM_SPARSE = 11
PSM_SPARSE_OSD = 12


def _pil_to_gray_np(img: Image.Image) -> np.ndarray:
    if img.mode != "L":
        img = img.convert("L")
    return np.asarray(img, dtype=np.uint8)


def vertical_valley_column_bounds(
    gray: np.ndarray,
    min_col_width_px: int = 40,
    valley_fraction: float = 0.28,
) -> list[tuple[int, int]]:
    """Split page into column x-ranges using vertical ink projection valleys."""
    h, w = gray.shape[:2]
    if w < 2 * min_col_width_px:
        return [(0, w)]

    ink = (gray < 200).astype(np.float32)
    proj = ink.sum(axis=0)
    if proj.max() <= 0:
        return [(0, w)]

    pnorm = proj / (proj.max() + 1e-6)
    # Local minima in the whitespace between columns
    splits: list[int] = [0]
    for x in range(2, w - 2):
        if pnorm[x] < valley_fraction and pnorm[x] <= pnorm[x - 1] and pnorm[x] <= pnorm[x + 1]:
            splits.append(x)
    splits.append(w)

    bounds: list[tuple[int, int]] = []
    for i in range(len(splits) - 1):
        a, b = splits[i], splits[i + 1]
        if b - a >= min_col_width_px:
            bounds.append((a, b))

    if len(bounds) < 2:
        return [(0, w)]
    return bounds


def score_ocr_text(text: str) -> float:
    """Heuristic quality score for comparing OCR variants (higher = better)."""
    if not text:
        return 0.0
    s = text.strip()
    ar, lat = script_ratio_from_text(s)
    letters = sum(1 for c in s if c.isalpha() or ("\u0530" <= c <= "\u058f"))
    letter_ratio = letters / max(len(s), 1)
    # Penalize pipe-heavy garbage common in failed table OCR
    noise = s.count("|") + s.count("\x00")
    return (ar + lat) * 50.0 + letter_ratio * 30.0 + min(len(s), 8000) * 0.02 - noise * 2.0


def ocr_image_string(
    pil_image: Image.Image,
    lang: str,
    psm: int,
    binarization: str = "sauvola",
) -> str:
    """Run preprocess + Tesseract image_to_string."""
    method = BinarizationMethod(binarization)
    pre = preprocess(pil_image, method=method)
    cfg = build_config(psm=psm)
    raw = pytesseract.image_to_string(pre, lang=lang, config=cfg)
    return postprocess(raw) if raw else ""


def ocr_column_strips(
    pil_image: Image.Image,
    lang: str,
    psm: int = PSM_BLOCK,
    binarization: str = "sauvola",
    min_col_width_px: int = 50,
) -> str:
    """Crop vertical columns left-to-right, OCR each, join with newlines."""
    method = BinarizationMethod(binarization)
    pre = preprocess(pil_image, method=method)
    arr = _pil_to_gray_np(pre)
    bounds = vertical_valley_column_bounds(arr, min_col_width_px=min_col_width_px)
    if len(bounds) == 1:
        return ocr_image_string(pil_image, lang, psm=psm, binarization=binarization)

    parts: list[str] = []
    for x0, x1 in bounds:
        crop = pil_image.crop((x0, 0, x1, pil_image.height))
        parts.append(ocr_image_string(crop, lang, psm=psm, binarization=binarization))
    return "\n\n".join(p for p in parts if p.strip())


def best_sparse_psm_variant(
    pil_image: Image.Image,
    lang: str,
    binarization: str = "sauvola",
) -> tuple[str, int]:
    """Priority C: try PSM 6, 11, 12; return best-scoring text and winning PSM."""
    candidates: list[tuple[float, str, int]] = []
    for psm in (PSM_BLOCK, PSM_SPARSE, PSM_SPARSE_OSD):
        try:
            txt = ocr_image_string(pil_image, lang, psm=psm, binarization=binarization)
            sc = score_ocr_text(txt)
            candidates.append((sc, txt, psm))
        except Exception as exc:
            logger.debug("PSM %d failed: %s", psm, exc)
    if not candidates:
        return "", PSM_BLOCK
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_sc, best_txt, best_psm = candidates[0]
    logger.debug("Best sparse PSM variant: psm=%d score=%.1f", best_psm, best_sc)
    return best_txt, best_psm


def reassemble_reading_order_from_boxes(
    pil_image: Image.Image,
    lang: str,
    psm: int = PSM_SPARSE,
    binarization: str = "sauvola",
) -> str:
    """Priority D (light): use Tesseract word boxes, sort by (y,x), join words.

    Helps when image_to_string reading order is wrong on sparse layouts.
    """
    method = BinarizationMethod(binarization)
    pre = preprocess(pil_image, method=method)
    cfg = build_config(psm=psm)
    try:
        data = pytesseract.image_to_data(
            pre, lang=lang, config=cfg, output_type=pytesseract.Output.DICT
        )
    except Exception as exc:
        logger.debug("image_to_data failed: %s", exc)
        return ""

    n = len(data.get("text", []))
    words: list[tuple[int, int, str]] = []
    for i in range(n):
        t = (data["text"][i] or "").strip()
        if not t:
            continue
        try:
            conf = int(data["conf"][i])
        except (ValueError, KeyError, IndexError):
            conf = 0
        if conf < 0:
            continue
        left = int(data["left"][i])
        top = int(data["top"][i])
        words.append((top, left, t))

    if not words:
        return ""

    # Bucket into lines by y (within tolerance)
    words.sort(key=lambda w: (w[0], w[1]))
    line_tol = max(12, pil_image.height // 80)
    lines: list[list[tuple[int, str]]] = []
    current_y = -1
    for top, left, t in words:
        if current_y < 0 or abs(top - current_y) > line_tol:
            lines.append([])
            current_y = top
        lines[-1].append((left, t))

    out_lines: list[str] = []
    for line in lines:
        line.sort(key=lambda x: x[0])
        out_lines.append(" ".join(w for _, w in line))
    return postprocess("\n".join(out_lines))


def suggest_table_like_heuristic(pil_image: Image.Image, binarization: str = "sauvola") -> bool:
    """Rough heuristic: wide page + deep vertical valleys => likely multi-column."""
    method = BinarizationMethod(binarization)
    pre = preprocess(pil_image, method=method)
    arr = _pil_to_gray_np(pre)
    h, w = arr.shape[:2]
    if w < 600:
        return False
    bounds = vertical_valley_column_bounds(arr, min_col_width_px=max(30, w // 12))
    return len(bounds) >= 3


def run_layout_fallbacks(
    pil_image: Image.Image,
    lang: str,
    binarization: str = "sauvola",
    force_columns: bool = False,
) -> tuple[str, str]:
    """Run B/C/D strategies; return (best_text, method_name).

    method_name is one of: columns, sparse_psm, word_boxes, fullpage.
    """
    candidates: list[tuple[float, str, str]] = []

    full = ocr_image_string(pil_image, lang, psm=PSM_BLOCK, binarization=binarization)
    candidates.append((score_ocr_text(full), full, "fullpage_psm6"))

    table_like = force_columns or suggest_table_like_heuristic(pil_image, binarization)
    if table_like:
        col_txt = ocr_column_strips(pil_image, lang, psm=PSM_BLOCK, binarization=binarization)
        candidates.append((score_ocr_text(col_txt), col_txt, "columns"))

    sp_txt, _psm = best_sparse_psm_variant(pil_image, lang, binarization=binarization)
    candidates.append((score_ocr_text(sp_txt), sp_txt, "sparse_psm_best"))

    box_txt = reassemble_reading_order_from_boxes(pil_image, lang, psm=PSM_SPARSE, binarization=binarization)
    candidates.append((score_ocr_text(box_txt), box_txt, "word_boxes_order"))

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_text, name = candidates[0]
    logger.info("Layout fallback winner: %s (score=%.1f)", name, best_score)
    return best_text, name
