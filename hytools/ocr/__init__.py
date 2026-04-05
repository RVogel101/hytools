"""OCR sub-package: PDF → image → Tesseract → postprocessed text.

Public API:
- ocr_pdf: full pipeline (PDF path → text files in output dir)
- preprocess: image preprocessing (binarization, deskew)
- postprocess: raw Tesseract text cleanup
- try_text_layer_page / run_layout_fallbacks / try_vector_tables: sparse layout and table hooks

All symbols are lazy-loaded on first access for faster import of the hytools package.
"""

import importlib as _importlib

# Map of public symbol → (module_name, symbol_name)
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "run_layout_fallbacks": ("layout_strategies", "run_layout_fallbacks"),
    "score_ocr_text": ("layout_strategies", "score_ocr_text"),
    "vertical_valley_column_bounds": ("layout_strategies", "vertical_valley_column_bounds"),
    "armcor_correct": ("armcor", "armcor_correct"),
    "load_armcor_frequencies": ("armcor", "load_armcor_frequencies"),
    "classical_ocr_image": ("classical_ocr", "classical_ocr_image"),
    "is_classical_available": ("classical_ocr", "is_classical_available"),
    "is_kraken_available": ("hybrid_ocr", "is_kraken_available"),
    "is_ocrmypdf_available": ("hybrid_ocr", "is_ocrmypdf_available"),
    "kraken_ocr_image": ("hybrid_ocr", "kraken_ocr_image"),
    "ocrmypdf_page": ("hybrid_ocr", "ocrmypdf_page"),
    "is_ml_corrector_available": ("ml_corrector", "is_ml_corrector_available"),
    "ml_correct_text": ("ml_corrector", "ml_correct_text"),
    "check_token": ("nayiri_spellcheck", "check_token"),
    "load_nayiri_wordset": ("nayiri_spellcheck", "load_nayiri_wordset"),
    "reset_wordset": ("nayiri_spellcheck", "reset_wordset"),
    "OCRAttempt": ("ocr_metrics", "OCRAttempt"),
    "OCRPageMetric": ("ocr_metrics", "OCRPageMetric"),
    "new_run_id": ("ocr_metrics", "new_run_id"),
    "write_page_metric": ("ocr_metrics", "write_page_metric"),
    "PageStrategy": ("page_classifier", "PageStrategy"),
    "PageType": ("page_classifier", "PageType"),
    "classify_page": ("page_classifier", "classify_page"),
    "extract_tables_camelot": ("pdf_tables_vector", "extract_tables_camelot"),
    "extract_tables_tabula": ("pdf_tables_vector", "extract_tables_tabula"),
    "try_vector_tables": ("pdf_tables_vector", "try_vector_tables"),
    "TextLayerProbeResult": ("pdf_text_layer", "TextLayerProbeResult"),
    "is_acceptable_text_layer": ("pdf_text_layer", "is_acceptable_text_layer"),
    "parse_use_text_layer_setting": ("pdf_text_layer", "parse_use_text_layer_setting"),
    "probe_text_layer_policy": ("pdf_text_layer", "probe_text_layer_policy"),
    "try_text_layer_page": ("pdf_text_layer", "try_text_layer_page"),
    "ocr_pdf": ("pipeline", "ocr_pdf"),
    "detect_stroke_thinning": ("preprocessor", "detect_stroke_thinning"),
    "estimate_stroke_width": ("preprocessor", "estimate_stroke_width"),
    "preprocess": ("preprocessor", "preprocess"),
    "thicken_strokes": ("preprocessor", "thicken_strokes"),
    "apply_confusion_corrections": ("postprocessor", "apply_confusion_corrections"),
    "postprocess": ("postprocessor", "postprocess"),
    "ReviewItem": ("review_queue", "ReviewItem"),
    "enqueue_for_review": ("review_queue", "enqueue_for_review"),
    "make_thumbnail": ("review_queue", "make_thumbnail"),
    "RunMonitor": ("run_monitor", "RunMonitor"),
    "is_surya_available": ("surya_engine", "is_surya_available"),
    "surya_ocr_image": ("surya_engine", "surya_ocr_image"),
    "surya_ocr_image_with_confidence": ("surya_engine", "surya_ocr_image_with_confidence"),
    "build_zones": ("zone_splitter", "build_zones"),
    "is_mixed_page": ("zone_splitter", "is_mixed_page"),
    "zone_ocr_page": ("zone_splitter", "zone_ocr_page"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        module = _importlib.import_module(f".{module_name}", __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
