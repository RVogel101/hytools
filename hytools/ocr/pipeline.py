"""End-to-end OCR pipeline: PDF → preprocessed images → Tesseract → clean text.

Supports adaptive DPI: probe first page, measure character height, choose DPI
so letter height falls in Tesseract's optimal 20–30 px range.

Usage::

    python -m src.ocr.pipeline                   # process all PDFs in data/raw
    python -m src.ocr.pipeline path/to/file.pdf  # process a single PDF
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pytesseract  # type: ignore
import yaml
from pdf2image import convert_from_path  # type: ignore[reportMissingImports]

from .postprocessor import postprocess
from .preprocessor import BinarizationMethod, preprocess
from .tesseract_config import (
    TESSERACT_LANG,
    TESSERACT_LANG_ARMENIAN,
    TESSERACT_LANG_MIXED,
    TESSERACT_LANG_ENGLISH,
    PSM_BLOCK,
    build_config,
    script_ratio_from_text,
    choose_tesseract_lang_from_ratio,
)

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"

# Tesseract optimal: 20–30 px letter height
_TARGET_HEIGHT_PX = 25
_MIN_DPI = 150
_MAX_DPI = 600


def _load_config() -> dict:
    p = _SETTINGS_PATH
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def _estimate_character_height(image: Any, lang: str, tess_config: str) -> float | None:
    """Run Tesseract image_to_data and return median word bounding-box height.

    Returns None if no valid heights found.
    """
    data = pytesseract.image_to_data(image, lang=lang, config=tess_config, output_type=pytesseract.Output.DICT)
    heights = [
        int(h) for h in data.get("height", [])
        if isinstance(h, (int, float)) and 5 <= int(h) <= 200
    ]
    if not heights:
        return None
    heights.sort()
    return float(heights[len(heights) // 2])


def choose_adaptive_dpi(
    measured_height_px: float,
    probe_dpi: int = 200,
    target_height: int = _TARGET_HEIGHT_PX,
    min_dpi: int = _MIN_DPI,
    max_dpi: int = _MAX_DPI,
) -> int:
    """Choose DPI so letter height approaches target (20–30 px optimal for Tesseract).

    Formula: dpi = probe_dpi * (target / measured)
    """
    if measured_height_px <= 0:
        return probe_dpi
    dpi = int(probe_dpi * (target_height / measured_height_px))
    return max(min_dpi, min(max_dpi, dpi))


def _resolve_dpi(
    pdf_path: Path,
    dpi: int,
    lang: str,
    tess_config: str,
    adaptive: bool,
    font_hint: str | None,
    probe_dpi: int,
    detect_cursive: bool = False,
    cursive_threshold: float = 0.5,
) -> int:
    """Resolve final DPI: fixed, font hint override, or adaptive from probe."""
    # Font hint overrides (for known tiny/cursive sources)
    if font_hint == "tiny":
        return min(_MAX_DPI, max(400, dpi))
    if font_hint == "cursive":
        return min(_MAX_DPI, max(300, dpi))
    if font_hint == "normal":
        return max(_MIN_DPI, min(300, dpi))

    if not adaptive:
        return dpi

    # Adaptive: probe first page
    try:
        images = convert_from_path(str(pdf_path), dpi=probe_dpi, first_page=1, last_page=1)
    except Exception as exc:
        logger.warning("Probe render failed, using fixed DPI: %s", exc)
        return dpi

    if not images:
        return dpi

    preprocessed = preprocess(
        images[0],
        method=BinarizationMethod.SAUVOLA,
        detect_cursive=detect_cursive,
        cursive_threshold=cursive_threshold,
    )
    height = _estimate_character_height(preprocessed, lang, tess_config)
    if height is None:
        logger.debug("Could not estimate height, using fixed DPI %d", dpi)
        return dpi

    chosen = choose_adaptive_dpi(height, probe_dpi=probe_dpi)
    logger.info("Adaptive DPI: measured %.1f px at %d DPI → using %d DPI", height, probe_dpi, chosen)
    return chosen


def ocr_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 300,
    lang: str = TESSERACT_LANG,
    binarization: str = "sauvola",
    confidence_threshold: int = 60,
    adaptive_dpi: bool = False,
    font_hint: str | None = None,
    probe_dpi: int = 200,
    detect_cursive: bool = False,
    cursive_threshold: float = 0.5,
    per_page_lang: str = "off",
    psm: int = 3,
    tesseract_lang_armenian: str = TESSERACT_LANG_ARMENIAN,
    tesseract_lang_mixed: str = TESSERACT_LANG_MIXED,
    tesseract_lang_english: str = TESSERACT_LANG_ENGLISH,
    script_armenian_threshold: float = 0.9,
    script_english_threshold: float = 0.9,
) -> Path:
    """OCR a single PDF and write one .txt file per page.

    Parameters
    ----------
    pdf_path:
        Path to the input PDF.
    output_dir:
        Directory where per-page ``.txt`` files will be written.
    dpi:
        Resolution for rasterizing PDF pages (used when adaptive_dpi=False or as fallback).
    lang:
        Tesseract language string (e.g. ``"hye+eng"``). Used when per_page_lang is "off" or a fixed hint.
    binarization:
        One of ``"sauvola"``, ``"niblack"``, or ``"otsu"``.
    confidence_threshold:
        Pages whose mean Tesseract confidence is below this value are skipped.
    adaptive_dpi:
        If True, probe first page to measure character height and choose DPI
        so letter height falls in 20–30 px (optimal for Tesseract).
    font_hint:
        Override: "tiny" (400–600 DPI), "normal" (200–300), "cursive" (300–400).
    probe_dpi:
        DPI for probe pass when adaptive_dpi=True.
    detect_cursive:
        Auto-detect cursive and apply cursive-mode preprocessing when above threshold.
    cursive_threshold:
        Cursive likelihood score above which to use cursive-mode preprocessing.
    per_page_lang:
        "off" = use single lang for all pages; "auto" = detect script ratio per page and choose
        hye / hye+eng / eng; "hye" | "hye+eng" | "eng" = force that language for all pages.
    psm:
        Tesseract page segmentation mode (3=auto, 6=uniform block; 6 often better for textbook body text).
    tesseract_lang_armenian, tesseract_lang_mixed, tesseract_lang_english:
        Language strings used when per_page_lang is "auto" (and for fixed "hye"/"hye+eng"/"eng").
    script_armenian_threshold, script_english_threshold:
        When per_page_lang is "auto", Armenian ratio >= this → Armenian-only; Latin >= this → English-only.

    Returns
    -------
    Path
        The *output_dir* where results were written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    method = BinarizationMethod(binarization)
    tess_config = build_config(psm=psm)

    dpi = _resolve_dpi(
        pdf_path, dpi, lang, tess_config, adaptive_dpi, font_hint, probe_dpi,
        detect_cursive=detect_cursive,
        cursive_threshold=cursive_threshold,
    )

    logger.info("Rasterizing %s at %d DPI…", pdf_path.name, dpi)
    images = convert_from_path(str(pdf_path), dpi=dpi)
    logger.info("  %d pages found", len(images))

    for page_num, image in enumerate(images, start=1):
        out_txt = output_dir / f"page_{page_num:04d}.txt"
        if out_txt.exists():
            logger.debug("  Page %d already processed, skipping", page_num)
            continue

        preprocessed = preprocess(
            image,
            method=method,
            detect_cursive=detect_cursive,
            cursive_threshold=cursive_threshold,
        )

        # Per-page language: "off" | "auto" | "hye" | "hye+eng" | "eng"
        page_lang = lang
        if per_page_lang == "auto":
            # Probe the page with mixed languages to estimate script ratios
            probe_text = pytesseract.image_to_string(
                preprocessed, lang=tesseract_lang_mixed, config=tess_config
            )
            # Also get probe confidences to detect low-confidence misreads
            probe_data = pytesseract.image_to_data(
                preprocessed, lang=tesseract_lang_mixed, config=tess_config, output_type=pytesseract.Output.DICT
            )
            probe_confs = [c for c in probe_data.get("conf", []) if isinstance(c, (int, float)) and c >= 0]
            probe_mean_conf = sum(probe_confs) / len(probe_confs) if probe_confs else 0

            ar_ratio, lat_ratio = script_ratio_from_text(probe_text)

            # If probe confidence is low, prefer English when Armenian appears dominant
            # but with low confidence (likely a misread), or when Latin ratio exceeds Armenian.
            if probe_mean_conf < 50:
                # Prefer mixed-mode unless a script shows overwhelming dominance
                if ar_ratio > 0.8 and lat_ratio < 0.2:
                    page_lang = tesseract_lang_mixed if ar_ratio < 0.95 else tesseract_lang_armenian
                    logger.debug("  Page %d: low probe confidence %.1f and high ar_ratio %.2f → forcing %s", page_num, probe_mean_conf, ar_ratio, page_lang)
                elif lat_ratio > ar_ratio:
                    page_lang = tesseract_lang_mixed if lat_ratio < 0.95 else tesseract_lang_english
                    logger.debug("  Page %d: low probe confidence %.1f and lat>ar (%.2f>%.2f) → forcing %s", page_num, probe_mean_conf, lat_ratio, ar_ratio, page_lang)
                else:
                    page_lang = choose_tesseract_lang_from_ratio(
                        ar_ratio,
                        lat_ratio,
                        armenian_only_threshold=script_armenian_threshold,
                        english_only_threshold=script_english_threshold,
                        lang_armenian=tesseract_lang_armenian,
                        lang_mixed=tesseract_lang_mixed,
                        lang_english=tesseract_lang_english,
                    )
            else:
                page_lang = choose_tesseract_lang_from_ratio(
                    ar_ratio,
                    lat_ratio,
                    armenian_only_threshold=script_armenian_threshold,
                    english_only_threshold=script_english_threshold,
                    lang_armenian=tesseract_lang_armenian,
                    lang_mixed=tesseract_lang_mixed,
                    lang_english=tesseract_lang_english,
                )
            logger.debug("  Page %d: script ratio ar=%.2f lat=%.2f probe_conf=%.1f → lang=%s", page_num, ar_ratio, lat_ratio, probe_mean_conf, page_lang)
        elif per_page_lang in ("hye", "hye+eng", "eng"):
            page_lang = (
                tesseract_lang_armenian if per_page_lang == "hye" else
                tesseract_lang_english if per_page_lang == "eng" else
                tesseract_lang_mixed
            )

        # Run Tesseract
        data = pytesseract.image_to_data(
            preprocessed,
            lang=page_lang,
            config=tess_config,
            output_type=pytesseract.Output.DICT,
        )
        confidences = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
        mean_conf = sum(confidences) / len(confidences) if confidences else 0

        if mean_conf < confidence_threshold:
            logger.warning(
                "  Page %d: low confidence %.1f (threshold %d), skipping",
                page_num,
                mean_conf,
                confidence_threshold,
            )
            continue

        raw_text = pytesseract.image_to_string(preprocessed, lang=page_lang, config=tess_config)
        clean_text = postprocess(raw_text)
        out_txt.write_text(clean_text, encoding="utf-8")
        logger.debug("  Page %d: conf=%.1f, chars=%d, lang=%s", page_num, mean_conf, len(clean_text), page_lang)

    return output_dir


def run(config: dict | None = None, pdf_path: Path | None = None) -> None:
    """Process all PDFs in raw_dir or a single *pdf_path*."""
    cfg = config or _load_config()
    paths = cfg.get("paths", {})
    raw_dir = Path(paths.get("raw_dir", "data/raw"))
    ocr_dir = Path(paths.get("ocr_output_dir", "data/ocr_output"))
    ocr_cfg = cfg.get("ocr", {})

    pdfs = [pdf_path] if pdf_path else list(raw_dir.rglob("*.pdf"))
    logger.info("Found %d PDFs to process", len(pdfs))

    for pdf in pdfs:
        rel = pdf.relative_to(raw_dir) if pdf.is_relative_to(raw_dir) else Path(pdf.name)
        out = ocr_dir / rel.with_suffix("")
        try:
            ocr_pdf(
                pdf,
                out,
                dpi=ocr_cfg.get("dpi", 300),
                lang=ocr_cfg.get("tesseract_lang", TESSERACT_LANG),
                binarization=ocr_cfg.get("binarization", "sauvola"),
                confidence_threshold=ocr_cfg.get("confidence_threshold", 60),
                adaptive_dpi=ocr_cfg.get("adaptive_dpi", False),
                font_hint=ocr_cfg.get("font_hint"),
                probe_dpi=ocr_cfg.get("probe_dpi", 200),
                psm=ocr_cfg.get("psm", 3),
                detect_cursive=ocr_cfg.get("detect_cursive", False),
                cursive_threshold=ocr_cfg.get("cursive_threshold", 0.5),
                per_page_lang=ocr_cfg.get("per_page_lang", "off"),
                tesseract_lang_armenian=ocr_cfg.get("tesseract_lang_armenian", TESSERACT_LANG_ARMENIAN),
                tesseract_lang_mixed=ocr_cfg.get("tesseract_lang_mixed", TESSERACT_LANG_MIXED),
                tesseract_lang_english=ocr_cfg.get("tesseract_lang_english", TESSERACT_LANG_ENGLISH),
                script_armenian_threshold=ocr_cfg.get("script_armenian_threshold", 0.9),
                script_english_threshold=ocr_cfg.get("script_english_threshold", 0.9),
            )
        except Exception as exc:
            logger.error("Failed to OCR %s: %s", pdf, exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run(pdf_path=path_arg)
