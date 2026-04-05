"""End-to-end OCR pipeline: PDF → preprocessed images → Tesseract → clean text.

Supports adaptive DPI: probe first page, measure character height, choose DPI
so letter height falls in Tesseract's optimal 20–30 px range.

Usage::

    python -m hytools.ocr.pipeline                    # all PDFs under raw_dir (see settings)
    python -m hytools.ocr.pipeline path/to/file.pdf  # one PDF
    python -m hytools.ocr.pipeline file.pdf --overwrite  # redo even if page_####.txt exists
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from pdf2image import convert_from_path  # type: ignore[reportMissingImports]

from ._tesseract_lazy import get_pytesseract
from .layout_strategies import run_layout_fallbacks, score_ocr_text
from .ocr_metrics import OCRAttempt, OCRPageMetric, new_run_id, write_page_metric
from .review_queue import (
    ReviewItem,
    enqueue_for_review,
    make_thumbnail,
    PRIORITY_BELOW_CONFIDENCE,
    PRIORITY_EMPTY_FALLBACK,
    PRIORITY_NON_TEXT,
)
from .pdf_tables_vector import try_vector_tables as extract_vector_tables_from_pdf
from .pdf_text_layer import (
    parse_use_text_layer_setting,
    probe_text_layer_policy,
    try_text_layer_page,
)
from .postprocessor import postprocess
from .page_classifier import PageType, classify_page
from .preprocessor import BinarizationMethod, preprocess
from .surya_engine import is_surya_available, surya_ocr_image
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
from .zone_splitter import zone_ocr_page
from .classical_ocr import (
    classical_ocr_image,
    is_classical_available,
    DEFAULT_CLASSICAL_LANG,
    DEFAULT_CLASSICAL_THRESHOLD,
)
from .hybrid_ocr import (
    is_ocrmypdf_available,
    is_kraken_available,
    ocrmypdf_page,
    kraken_ocr_image,
)
from .ml_corrector import is_ml_corrector_available, ml_correct_text
from .armcor import armcor_correct, load_armcor_frequencies
from .run_monitor import RunMonitor, DEFAULT_ALERT_THRESHOLD, DEFAULT_MIN_PAGES

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
    pt = get_pytesseract()
    data = pt.image_to_data(image, lang=lang, config=tess_config, output_type=pt.Output.DICT)
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
    use_text_layer: bool | str = False,
    overwrite: bool = False,
    layout_fallback: bool = False,
    try_vector_tables: bool = False,
    vector_tables_prefer: str = "camelot",
    use_surya: bool | str = "auto",
    zone_ocr: bool | str = "auto",
    classify_pages: bool | str = "auto",
    stroke_thicken: bool | str = False,
    stroke_thin_threshold: float = 2.5,
    stroke_thicken_iterations: int = 1,
    stroke_thicken_kernel: int = 2,
    classical_ocr: bool | str = "auto",
    classical_lang: str = DEFAULT_CLASSICAL_LANG,
    classical_threshold: float = DEFAULT_CLASSICAL_THRESHOLD,
    use_ocrmypdf: bool | str = "auto",
    use_kraken: bool | str = "auto",
    kraken_model: str = "",
    ml_corrector: bool | str = "auto",
    ml_corrector_model: str = "",
    ml_corrector_max_length: int = 512,
    armcor_correction: bool | str = "auto",
    armcor_freq_path: str = "",
    armcor_min_freq: int = 3,
    armcor_max_edit_distance: int = 1,
    monitor_alert_threshold: float = DEFAULT_ALERT_THRESHOLD,
    monitor_min_pages: int = DEFAULT_MIN_PAGES,
    db_client: Any | None = None,
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
    use_text_layer:
        ``True`` / ``False``, or ``\"auto\"`` to probe a few pages (spread across the PDF) and
        enable the text layer only when embedded text looks consistently structured (heuristic).
    overwrite:
        If True, re-process every page even when ``page_####.txt`` already exists.
    layout_fallback:
        If True, run column/sparse-PSM/word-box strategies and pick the best-scoring text (see layout_strategies).
    try_vector_tables:
        If True, append Camelot/Tabula table extracts for vector PDFs (optional deps).
    vector_tables_prefer:
        ``"camelot"`` or ``"tabula"`` — which library to try first.
    use_surya:
        Run Surya OCR as a parallel engine alongside Tesseract and keep the
        higher-scoring result per page.  ``True`` = always try Surya,
        ``"auto"`` = use Surya when the package is installed (default),
        ``False`` = Tesseract only.
    zone_ocr:
        Split mixed Armenian+English pages into script-specific zones and
        re-OCR each zone with the optimal single-language model.
        ``True`` = always attempt zone splitting on every page,
        ``"auto"`` = split only when per_page_lang is ``"auto"`` and the
        probe detects significant amounts of both scripts (default),
        ``False`` = disabled.
    classify_pages:
        Run the pre-OCR page classifier to route each page to the optimal
        strategy (lang, PSM, layout fallback, zone OCR).  ``True`` = always
        classify, ``"auto"`` = classify when per_page_lang is ``"auto"``
        (default), ``False`` = disabled.
    stroke_thicken:
        Morphological dilation for degraded / thin type.  ``True`` = always
        thicken, ``"auto"`` = detect thin strokes and thicken only when median
        stroke width is below *stroke_thin_threshold*, ``False`` = disabled
        (default).
    stroke_thin_threshold:
        Median stroke width (px) below which auto-detection triggers
        thickening (default 2.5).
    stroke_thicken_iterations:
        Number of dilation passes (default 1).
    stroke_thicken_kernel:
        Side length of the square structuring element in pixels (default 2).
    classical_ocr:
        Extra Tesseract pass with classical-orthography traineddata for
        stubborn pages whose best score is still below *classical_threshold*.
        ``True`` = always try, ``"auto"`` = try when the traineddata is
        installed (default), ``False`` = disabled.
    classical_lang:
        Tesseract language name for the classical model (default ``"hye_old"``).
    classical_threshold:
        Score below which the classical pass fires (default 15.0).
    monitor_alert_threshold:
        Fraction (0–1) of failed pages that triggers a warning alert
        (default 0.10 = 10 %).
    monitor_min_pages:
        Minimum total pages before alerting — avoids noise on tiny PDFs
        (default 3).
    db_client:
        Optional :class:`~hytools.integrations.database.mongodb_client.MongoDBCorpusClient`.
        When provided, per-page OCR metrics are written to the
        ``ocr_page_metrics`` collection.  See :mod:`hytools.ocr.ocr_metrics`
        for the full schema reference.

    Returns
    -------
    Path
        The *output_dir* where results were written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    method = BinarizationMethod(binarization)
    tess_config = build_config(psm=psm)

    # Metrics destination
    run_id = new_run_id()
    metrics_coll = db_client.ocr_page_metrics if db_client is not None else None
    review_coll = db_client.ocr_review_queue if db_client is not None else None
    alerts_coll = db_client.ocr_run_alerts if db_client is not None else None

    monitor = RunMonitor(
        run_id=run_id,
        pdf_name=pdf_path.name,
        alert_threshold=monitor_alert_threshold,
        min_pages=monitor_min_pages,
    )

    # Resolve zone OCR
    zone_ocr_enabled = False
    if zone_ocr == "auto":
        zone_ocr_enabled = per_page_lang == "auto"
    elif zone_ocr is True:
        zone_ocr_enabled = True
    if zone_ocr_enabled:
        logger.info("Zone OCR enabled — mixed-language pages will be split by script")

    # Resolve page classification
    classify_enabled = False
    if classify_pages == "auto":
        classify_enabled = per_page_lang == "auto"
    elif classify_pages is True:
        classify_enabled = True
    if classify_enabled:
        logger.info("Page classification enabled — routing pages to optimal OCR strategy")

    # Resolve Surya availability
    if use_surya == "auto":
        surya_enabled = is_surya_available()
    else:
        surya_enabled = bool(use_surya) and is_surya_available()
    if surya_enabled:
        logger.info("Surya OCR engine enabled — dual-engine scoring active")
    else:
        logger.debug("Surya OCR not available or disabled — Tesseract only")

    # Resolve classical orthography pass
    classical_enabled = False
    if classical_ocr == "auto":
        classical_enabled = is_classical_available(classical_lang)
    elif classical_ocr is True:
        classical_enabled = is_classical_available(classical_lang)
    if classical_enabled:
        logger.info("Classical OCR pass enabled (lang=%s, threshold=%.1f)",
                     classical_lang, classical_threshold)

    # Resolve hybrid OCR: OCRmyPDF
    ocrmypdf_enabled = False
    if use_ocrmypdf == "auto":
        ocrmypdf_enabled = is_ocrmypdf_available()
    elif use_ocrmypdf is True:
        ocrmypdf_enabled = is_ocrmypdf_available()
    if ocrmypdf_enabled:
        logger.info("OCRmyPDF engine enabled — hybrid OCR active")

    # Resolve hybrid OCR: Kraken
    kraken_enabled = False
    if use_kraken == "auto":
        kraken_enabled = is_kraken_available()
    elif use_kraken is True:
        kraken_enabled = is_kraken_available()
    if kraken_enabled:
        logger.info("Kraken OCR engine enabled — hybrid OCR active")

    # Resolve ML post-correction
    ml_corrector_enabled = False
    if ml_corrector == "auto":
        ml_corrector_enabled = is_ml_corrector_available(ml_corrector_model)
    elif ml_corrector is True:
        ml_corrector_enabled = is_ml_corrector_available(ml_corrector_model)
    if ml_corrector_enabled:
        logger.info("ML post-correction enabled (model=%s)", ml_corrector_model)

    # Resolve ArmCor corpus correction
    armcor_enabled = False
    armcor_freq: dict[str, int] = {}
    if armcor_correction == "auto":
        if armcor_freq_path:
            armcor_freq = load_armcor_frequencies(armcor_freq_path)
            armcor_enabled = bool(armcor_freq)
    elif armcor_correction is True:
        if armcor_freq_path:
            armcor_freq = load_armcor_frequencies(armcor_freq_path)
            armcor_enabled = bool(armcor_freq)
    if armcor_enabled:
        logger.info("ArmCor corpus correction enabled (%d words)", len(armcor_freq))

    layer_mode = parse_use_text_layer_setting(use_text_layer)
    if layer_mode == "auto":
        probe = probe_text_layer_policy(pdf_path)
        use_text_layer_effective = probe.recommend
        logger.info(
            "use_text_layer=auto → %s (%s) [sampled %d pages, %d acceptable, %d image-dominant]",
            use_text_layer_effective,
            probe.reason,
            probe.pages_sampled,
            probe.acceptable_pages,
            probe.image_dominant_pages,
        )
    else:
        use_text_layer_effective = bool(layer_mode)

    dpi = _resolve_dpi(
        pdf_path, dpi, lang, tess_config, adaptive_dpi, font_hint, probe_dpi,
        detect_cursive=detect_cursive,
        cursive_threshold=cursive_threshold,
    )

    logger.info("Rasterizing %s at %d DPI…", pdf_path.name, dpi)
    images = convert_from_path(str(pdf_path), dpi=dpi)
    logger.info("  %d pages found", len(images))

    if not overwrite:
        existing_pages = list(output_dir.glob("page_*.txt"))
        if existing_pages:
            logger.info(
                "Found %d existing page_*.txt file(s); they will be skipped. "
                "Use --overwrite / -f or ocr.overwrite=true to re-OCR all pages.",
                len(existing_pages),
            )

    for page_num, image in enumerate(images, start=1):
        out_txt = output_dir / f"page_{page_num:04d}.txt"
        if out_txt.exists() and not overwrite:
            logger.debug("  Page %d already processed, skipping", page_num)
            monitor.record("skipped")
            continue

        # Priority A: embedded text layer (skips OCR when acceptable)
        if use_text_layer_effective:
            layer = try_text_layer_page(pdf_path, page_num)
            if layer is not None:
                clean_text = postprocess(layer)
                if try_vector_tables:
                    vt = extract_vector_tables_from_pdf(
                        pdf_path,
                        page_num,
                        prefer=vector_tables_prefer,
                    )
                    if vt:
                        clean_text = f"{clean_text.rstrip()}\n\n--- vector tables ---\n{vt}".strip()
                out_txt.write_text(clean_text, encoding="utf-8")
                logger.debug(
                    "  Page %d: text layer, chars=%d",
                    page_num,
                    len(clean_text),
                )
                if metrics_coll is not None:
                    write_page_metric(metrics_coll, OCRPageMetric(
                        run_id=run_id, pdf_path=str(pdf_path), pdf_name=pdf_path.name,
                        page_num=page_num, status="text_layer", engine="text_layer",
                        mean_confidence=-1, char_count=len(clean_text),
                        word_count=len(clean_text.split()), lang=lang, dpi=dpi,
                        psm=psm, binarization=binarization,
                        font_hint=font_hint, adaptive_dpi=adaptive_dpi,
                        detect_cursive=detect_cursive,
                        vector_tables_appended=bool(try_vector_tables and "--- vector tables ---" in clean_text),
                        confidence_threshold=confidence_threshold,
                        attempts=[OCRAttempt(
                            engine="text_layer", char_count=len(clean_text), chosen=True,
                        )],
                    ))
                monitor.record("text_layer")
                continue

        preprocessed = preprocess(
            image,
            method=method,
            detect_cursive=detect_cursive,
            cursive_threshold=cursive_threshold,
            stroke_thicken=stroke_thicken,
            stroke_thin_threshold=stroke_thin_threshold,
            stroke_thicken_iterations=stroke_thicken_iterations,
            stroke_thicken_kernel=stroke_thicken_kernel,
        )

        # ── Pre-OCR page classification ──────────────────────────────────
        # Per-page mutable overrides (defaults from function args)
        page_layout_fallback = layout_fallback
        page_try_vector_tables = try_vector_tables
        page_zone_ocr = zone_ocr_enabled
        page_psm = psm
        page_tess_config = tess_config

        if classify_enabled:
            strategy = classify_page(image, binarization=binarization)
            logger.debug(
                "  Page %d: classified as %s (conf=%.2f)",
                page_num, strategy.page_type.value, strategy.confidence,
            )

            if strategy.page_type == PageType.NON_TEXT:
                # Write blank stub + sidecar
                out_txt.write_text("", encoding="utf-8")
                sidecar = out_txt.with_suffix(".json")
                sidecar.write_text(
                    json.dumps(
                        {
                            "status": "non_text",
                            "page_type": strategy.page_type.value,
                            "classifier_confidence": strategy.confidence,
                            "page_num": page_num,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                logger.info("  Page %d: non-text, writing blank stub", page_num)
                if metrics_coll is not None:
                    write_page_metric(metrics_coll, OCRPageMetric(
                        run_id=run_id, pdf_path=str(pdf_path), pdf_name=pdf_path.name,
                        page_num=page_num, status="non_text", engine="none",
                        mean_confidence=-1, char_count=0, word_count=0,
                        lang=lang, dpi=dpi, psm=psm, binarization=binarization,
                        font_hint=font_hint, adaptive_dpi=adaptive_dpi,
                        detect_cursive=detect_cursive,
                        page_type=strategy.page_type.value,
                        classifier_confidence=strategy.confidence,
                        confidence_threshold=confidence_threshold,
                    ))
                if review_coll is not None:
                    enqueue_for_review(review_coll, ReviewItem(
                        run_id=run_id, pdf_path=str(pdf_path),
                        pdf_name=pdf_path.name, page_num=page_num,
                        reason="non_text", priority=PRIORITY_NON_TEXT,
                        detail=f"page_type={strategy.page_type.value} conf={strategy.confidence:.2f}",
                        lang=lang, dpi=dpi,
                        thumbnail=make_thumbnail(image),
                    ))
                monitor.record("non_text")
                continue

            # Apply strategy overrides
            page_layout_fallback = strategy.layout_fallback or layout_fallback
            page_try_vector_tables = strategy.try_vector_tables or try_vector_tables
            page_zone_ocr = strategy.zone_ocr or zone_ocr_enabled
            if strategy.psm != psm:
                page_psm = strategy.psm
                page_tess_config = build_config(psm=page_psm)

        # Per-page language: "off" | "auto" | "hye" | "hye+eng" | "eng"
        # If page classifier already chose a specific lang with decent
        # confidence, use it directly and skip the expensive probe.
        page_lang = lang
        if classify_enabled and strategy.confidence >= 0.7:
            page_lang = strategy.lang
            logger.debug("  Page %d: lang=%s (from classifier, conf=%.2f)",
                         page_num, page_lang, strategy.confidence)
        elif per_page_lang == "auto":
            # Probe the page with mixed languages to estimate script ratios
            pt = get_pytesseract()
            probe_text = pt.image_to_string(
                preprocessed, lang=tesseract_lang_mixed, config=page_tess_config
            )
            # Also get probe confidences to detect low-confidence misreads
            probe_data = pt.image_to_data(
                preprocessed, lang=tesseract_lang_mixed, config=page_tess_config, output_type=pt.Output.DICT
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

        # Run Tesseract (optional B/C/D layout fallback)
        pt = get_pytesseract()
        data = pt.image_to_data(
            preprocessed,
            lang=page_lang,
            config=page_tess_config,
            output_type=pt.Output.DICT,
        )
        confidences = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
        mean_conf = sum(confidences) / len(confidences) if confidences else 0

        # Baseline confidence gate: layout_fallback can recover text when default PSM scores poorly
        if not page_layout_fallback and mean_conf < confidence_threshold:
            logger.warning(
                "  Page %d: low confidence %.1f (threshold %d), writing blank stub",
                page_num,
                mean_conf,
                confidence_threshold,
            )
            # Write empty text file + sidecar JSON so downstream tools know
            # this page was attempted but fell below the confidence threshold.
            out_txt.write_text("", encoding="utf-8")
            sidecar = out_txt.with_suffix(".json")
            sidecar.write_text(
                json.dumps(
                    {
                        "status": "below_confidence",
                        "mean_confidence": round(mean_conf, 2),
                        "threshold": confidence_threshold,
                        "page_num": page_num,
                        "lang": page_lang,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            if metrics_coll is not None:
                _cls_type = strategy.page_type.value if classify_enabled else None
                _cls_conf = strategy.confidence if classify_enabled else None
                write_page_metric(metrics_coll, OCRPageMetric(
                    run_id=run_id, pdf_path=str(pdf_path), pdf_name=pdf_path.name,
                    page_num=page_num, status="below_confidence", engine="none",
                    mean_confidence=round(mean_conf, 2), char_count=0, word_count=0,
                    lang=page_lang, dpi=dpi, psm=page_psm, binarization=binarization,
                    font_hint=font_hint, adaptive_dpi=adaptive_dpi,
                    detect_cursive=detect_cursive,
                    page_type=_cls_type, classifier_confidence=_cls_conf,
                    confidence_threshold=confidence_threshold,
                    attempts=[OCRAttempt(
                        engine="tesseract", lang=page_lang, psm=page_psm,
                        mean_confidence=round(mean_conf, 2), char_count=0,
                        chosen=False, detail="below_confidence gate",
                    )],
                ))
            if review_coll is not None:
                enqueue_for_review(review_coll, ReviewItem(
                    run_id=run_id, pdf_path=str(pdf_path),
                    pdf_name=pdf_path.name, page_num=page_num,
                    reason="below_confidence", priority=PRIORITY_BELOW_CONFIDENCE,
                    detail=f"mean_conf={mean_conf:.1f} threshold={confidence_threshold}",
                    mean_confidence=round(mean_conf, 2),
                    lang=page_lang, dpi=dpi,
                    thumbnail=make_thumbnail(image),
                ))
            monitor.record("below_confidence")
            continue

        if page_layout_fallback:
            raw_text, layout_name = run_layout_fallbacks(
                image,
                page_lang,
                binarization=binarization,
            )
            logger.debug("  Page %d: layout_fallback=%s", page_num, layout_name)
        else:
            raw_text = pt.image_to_string(preprocessed, lang=page_lang, config=page_tess_config)

        tess_text = postprocess(raw_text)

        # ── Attempt tracking ─────────────────────────────────────────────
        page_attempts: list[OCRAttempt] = []
        tess_score_val = score_ocr_text(tess_text)
        if page_layout_fallback:
            page_attempts.append(OCRAttempt(
                engine="layout_fallback", lang=page_lang, psm=page_psm,
                score=tess_score_val, mean_confidence=round(mean_conf, 2),
                char_count=len(tess_text), chosen=True, detail=layout_name,
            ))
        else:
            page_attempts.append(OCRAttempt(
                engine="tesseract", lang=page_lang, psm=page_psm,
                score=tess_score_val, mean_confidence=round(mean_conf, 2),
                char_count=len(tess_text), chosen=True,
            ))

        # Dual-engine: run Surya on the original (non-binarized) image and
        # keep whichever engine produces the higher-scoring text.
        chosen_engine = "tesseract"
        if surya_enabled:
            surya_text = surya_ocr_image(image)
            if surya_text is not None:
                surya_clean = postprocess(surya_text)
                tess_score = score_ocr_text(tess_text)
                surya_score = score_ocr_text(surya_clean)
                surya_won = surya_score > tess_score
                page_attempts.append(OCRAttempt(
                    engine="surya", score=surya_score,
                    char_count=len(surya_clean), chosen=surya_won,
                ))
                if surya_won:
                    # Mark prior attempt as not chosen
                    page_attempts[0] = OCRAttempt(
                        **{**page_attempts[0].to_dict(), "chosen": False},
                    )
                    tess_text = surya_clean
                    chosen_engine = "surya"
                logger.debug(
                    "  Page %d: tess_score=%.1f surya_score=%.1f → %s",
                    page_num, tess_score, surya_score, chosen_engine,
                )

        clean_text = tess_text

        # Zone OCR: on mixed pages, split into script-specific zones and
        # re-OCR each with the optimal single-language model.
        if page_zone_ocr:
            zone_text = zone_ocr_page(
                image,
                probe_lang=tesseract_lang_mixed,
                binarization=binarization,
                psm=psm,
                lang_armenian=tesseract_lang_armenian,
                lang_english=tesseract_lang_english,
                lang_mixed=tesseract_lang_mixed,
            )
            if zone_text is not None:
                zone_score = score_ocr_text(zone_text)
                current_score = score_ocr_text(clean_text)
                zone_won = zone_score > current_score
                page_attempts.append(OCRAttempt(
                    engine="zone_ocr", lang=tesseract_lang_mixed,
                    score=zone_score, char_count=len(zone_text), chosen=zone_won,
                ))
                if zone_won:
                    # Mark previous winner as not chosen
                    for i, a in enumerate(page_attempts[:-1]):
                        if a.chosen:
                            page_attempts[i] = OCRAttempt(
                                **{**a.to_dict(), "chosen": False},
                            )
                    clean_text = zone_text
                    chosen_engine = "zone_ocr"
                logger.debug(
                    "  Page %d: zone_score=%.1f vs current_score=%.1f → %s",
                    page_num, zone_score, current_score, chosen_engine,
                )

        # Hybrid OCR: OCRmyPDF engine
        if ocrmypdf_enabled:
            ocrmypdf_text = ocrmypdf_page(image, lang=page_lang, dpi=dpi)
            if ocrmypdf_text is not None:
                ocrmypdf_clean = postprocess(ocrmypdf_text)
                omp_score = score_ocr_text(ocrmypdf_clean)
                current_score = score_ocr_text(clean_text)
                omp_won = omp_score > current_score
                page_attempts.append(OCRAttempt(
                    engine="ocrmypdf", lang=page_lang,
                    score=omp_score, char_count=len(ocrmypdf_clean),
                    chosen=omp_won,
                ))
                if omp_won:
                    for i, a in enumerate(page_attempts[:-1]):
                        if a.chosen:
                            page_attempts[i] = OCRAttempt(
                                **{**a.to_dict(), "chosen": False},
                            )
                    clean_text = ocrmypdf_clean
                    chosen_engine = "ocrmypdf"
                logger.debug(
                    "  Page %d: ocrmypdf_score=%.1f vs current=%.1f → %s",
                    page_num, omp_score, current_score, chosen_engine,
                )

        # Hybrid OCR: Kraken engine
        if kraken_enabled:
            kraken_text = kraken_ocr_image(image, model_path=kraken_model)
            if kraken_text is not None:
                kraken_clean = postprocess(kraken_text)
                kr_score = score_ocr_text(kraken_clean)
                current_score = score_ocr_text(clean_text)
                kr_won = kr_score > current_score
                page_attempts.append(OCRAttempt(
                    engine="kraken", score=kr_score,
                    char_count=len(kraken_clean), chosen=kr_won,
                ))
                if kr_won:
                    for i, a in enumerate(page_attempts[:-1]):
                        if a.chosen:
                            page_attempts[i] = OCRAttempt(
                                **{**a.to_dict(), "chosen": False},
                            )
                    clean_text = kraken_clean
                    chosen_engine = "kraken"
                logger.debug(
                    "  Page %d: kraken_score=%.1f vs current=%.1f → %s",
                    page_num, kr_score, current_score, chosen_engine,
                )

        # Classical orthography pass: last-resort for stubborn pages
        if classical_enabled and score_ocr_text(clean_text) < classical_threshold:
            cls_result = classical_ocr_image(
                image, lang=classical_lang, psm=page_psm, binarization=binarization,
            )
            if cls_result is not None:
                cls_text, cls_conf = cls_result
                cls_clean = cls_text  # already postprocessed inside classical_ocr_image
                cls_score = score_ocr_text(cls_clean)
                current_score = score_ocr_text(clean_text)
                cls_won = cls_score > current_score
                page_attempts.append(OCRAttempt(
                    engine="classical", lang=classical_lang, psm=page_psm,
                    score=cls_score, mean_confidence=cls_conf,
                    char_count=len(cls_clean), chosen=cls_won,
                    detail=f"classical_threshold={classical_threshold}",
                ))
                if cls_won:
                    for i, a in enumerate(page_attempts[:-1]):
                        if a.chosen:
                            page_attempts[i] = OCRAttempt(
                                **{**a.to_dict(), "chosen": False},
                            )
                    clean_text = cls_clean
                    chosen_engine = "classical"
                logger.debug(
                    "  Page %d: classical_score=%.1f vs current=%.1f → %s",
                    page_num, cls_score, current_score, chosen_engine,
                )

        if page_layout_fallback and not clean_text.strip():
            logger.warning("  Page %d: layout fallback produced empty text, skipping", page_num)
            if metrics_coll is not None:
                _cls_type = strategy.page_type.value if classify_enabled else None
                _cls_conf = strategy.confidence if classify_enabled else None
                write_page_metric(metrics_coll, OCRPageMetric(
                    run_id=run_id, pdf_path=str(pdf_path), pdf_name=pdf_path.name,
                    page_num=page_num, status="empty_after_fallback", engine=chosen_engine,
                    mean_confidence=round(mean_conf, 2), char_count=0, word_count=0,
                    lang=page_lang, dpi=dpi, psm=page_psm, binarization=binarization,
                    font_hint=font_hint, adaptive_dpi=adaptive_dpi,
                    detect_cursive=detect_cursive,
                    page_type=_cls_type, classifier_confidence=_cls_conf,
                    layout_fallback_used=True,
                    confidence_threshold=confidence_threshold,
                    attempts=page_attempts,
                ))
            if review_coll is not None:
                enqueue_for_review(review_coll, ReviewItem(
                    run_id=run_id, pdf_path=str(pdf_path),
                    pdf_name=pdf_path.name, page_num=page_num,
                    reason="empty_after_fallback", priority=PRIORITY_EMPTY_FALLBACK,
                    detail=f"layout fallback produced empty text after {len(page_attempts)} attempts",
                    mean_confidence=round(mean_conf, 2),
                    lang=page_lang, dpi=dpi,
                    thumbnail=make_thumbnail(image),
                ))
            monitor.record("empty_after_fallback")
            continue

        if page_try_vector_tables:
            vt = extract_vector_tables_from_pdf(pdf_path, page_num, prefer=vector_tables_prefer)
            if vt:
                clean_text = f"{clean_text.rstrip()}\n\n--- vector tables ---\n{vt}".strip()

        # ── Post-correction passes ───────────────────────────────────────
        # ArmCor corpus-frequency correction
        if armcor_enabled and clean_text.strip():
            armcor_result = armcor_correct(
                clean_text, freq=armcor_freq,
                min_freq=armcor_min_freq, max_edit=armcor_max_edit_distance,
            )
            if armcor_result != clean_text:
                logger.debug("  Page %d: ArmCor corrected text", page_num)
                clean_text = armcor_result

        # ML-backed post-correction
        if ml_corrector_enabled and clean_text.strip():
            ml_result = ml_correct_text(
                clean_text, model_path=ml_corrector_model,
                max_length=ml_corrector_max_length,
            )
            if ml_result is not None:
                ml_score = score_ocr_text(ml_result)
                pre_score = score_ocr_text(clean_text)
                if ml_score >= pre_score:
                    logger.debug(
                        "  Page %d: ML correction improved score %.1f → %.1f",
                        page_num, pre_score, ml_score,
                    )
                    clean_text = ml_result
                else:
                    logger.debug(
                        "  Page %d: ML correction rejected (%.1f < %.1f)",
                        page_num, ml_score, pre_score,
                    )

        out_txt.write_text(clean_text, encoding="utf-8")
        logger.debug("  Page %d: engine=%s conf=%.1f, chars=%d, lang=%s", page_num, chosen_engine, mean_conf, len(clean_text), page_lang)

        if metrics_coll is not None:
            _cls_type = strategy.page_type.value if classify_enabled else None
            _cls_conf = strategy.confidence if classify_enabled else None
            _vt_appended = "--- vector tables ---" in clean_text
            write_page_metric(metrics_coll, OCRPageMetric(
                run_id=run_id, pdf_path=str(pdf_path), pdf_name=pdf_path.name,
                page_num=page_num, status="success", engine=chosen_engine,
                mean_confidence=round(mean_conf, 2),
                char_count=len(clean_text), word_count=len(clean_text.split()),
                lang=page_lang, dpi=dpi, psm=page_psm, binarization=binarization,
                font_hint=font_hint, adaptive_dpi=adaptive_dpi,
                detect_cursive=detect_cursive,
                page_type=_cls_type, classifier_confidence=_cls_conf,
                layout_fallback_used=page_layout_fallback,
                zone_ocr_used=(chosen_engine == "zone_ocr"),
                vector_tables_appended=_vt_appended,
                confidence_threshold=confidence_threshold,
                attempts=page_attempts,
            ))

        monitor.record("success")

    # ── Post-run monitoring ──────────────────────────────────────────────
    monitor.check_alerts(collection=alerts_coll)

    return output_dir


def run(
    config: dict | None = None,
    pdf_path: Path | None = None,
    overwrite: bool = False,
) -> None:
    """Process all PDFs in raw_dir or a single *pdf_path*."""
    cfg = config or _load_config()
    paths = cfg.get("paths", {})
    raw_dir = Path(paths.get("raw_dir", "data/raw"))
    ocr_dir = Path(paths.get("ocr_output_dir", "data/ocr_output"))
    ocr_cfg = cfg.get("ocr", {})
    do_overwrite = bool(overwrite or ocr_cfg.get("overwrite", False))

    # Open MongoDB connection if configured
    db_client = None
    db_cfg = cfg.get("database", {})
    if db_cfg.get("use_mongodb", False):
        try:
            from hytools.integrations.database.mongodb_client import MongoDBCorpusClient
            uri = db_cfg.get("mongodb_uri", "mongodb://localhost:27017/")
            db_name = db_cfg.get("mongodb_database", "western_armenian_corpus")
            db_client = MongoDBCorpusClient(uri=uri, database_name=db_name)
            db_client.connect()
            logger.info("OCR metrics will be written to MongoDB: %s", db_name)
        except Exception as exc:
            logger.warning("MongoDB unavailable — OCR metrics will not be persisted: %s", exc)
            db_client = None

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
                use_text_layer=ocr_cfg.get("use_text_layer", False),
                overwrite=do_overwrite,
                layout_fallback=ocr_cfg.get("layout_fallback", False),
                try_vector_tables=ocr_cfg.get("try_vector_tables", False),
                vector_tables_prefer=ocr_cfg.get("vector_tables_prefer", "camelot"),
                use_surya=ocr_cfg.get('use_surya', 'auto'),
                zone_ocr=ocr_cfg.get('zone_ocr', 'auto'),
                classify_pages=ocr_cfg.get('classify_pages', 'auto'),
                stroke_thicken=ocr_cfg.get('stroke_thicken', False),
                stroke_thin_threshold=ocr_cfg.get('stroke_thin_threshold', 2.5),
                stroke_thicken_iterations=ocr_cfg.get('stroke_thicken_iterations', 1),
                stroke_thicken_kernel=ocr_cfg.get('stroke_thicken_kernel', 2),
                classical_ocr=ocr_cfg.get('classical_ocr', 'auto'),
                classical_lang=ocr_cfg.get('classical_lang', DEFAULT_CLASSICAL_LANG),
                classical_threshold=ocr_cfg.get('classical_threshold', DEFAULT_CLASSICAL_THRESHOLD),
                use_ocrmypdf=ocr_cfg.get('use_ocrmypdf', 'auto'),
                use_kraken=ocr_cfg.get('use_kraken', 'auto'),
                kraken_model=ocr_cfg.get('kraken_model', ''),
                ml_corrector=ocr_cfg.get('ml_corrector', 'auto'),
                ml_corrector_model=ocr_cfg.get('ml_corrector_model', ''),
                ml_corrector_max_length=ocr_cfg.get('ml_corrector_max_length', 512),
                armcor_correction=ocr_cfg.get('armcor_correction', 'auto'),
                armcor_freq_path=ocr_cfg.get('armcor_freq_path', ''),
                armcor_min_freq=ocr_cfg.get('armcor_min_freq', 3),
                armcor_max_edit_distance=ocr_cfg.get('armcor_max_edit_distance', 1),
                monitor_alert_threshold=ocr_cfg.get('monitor_alert_threshold', DEFAULT_ALERT_THRESHOLD),
                monitor_min_pages=ocr_cfg.get('monitor_min_pages', DEFAULT_MIN_PAGES),
                db_client=db_client,
            )
        except Exception as exc:
            logger.error("Failed to OCR %s: %s", pdf, exc)

    if db_client is not None:
        db_client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="OCR PDFs to per-page page_####.txt files.")
    parser.add_argument(
        "pdf",
        nargs="?",
        type=Path,
        help="Path to a PDF (omit to process all PDFs under raw_dir from settings)",
    )
    parser.add_argument(
        "--overwrite",
        "-f",
        action="store_true",
        help="Re-run every page even if page_####.txt already exists",
    )
    args = parser.parse_args()
    run(pdf_path=args.pdf, overwrite=args.overwrite)
