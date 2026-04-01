"""OCR sub-package: PDF → image → Tesseract → postprocessed text.

Public API:
- ocr_pdf: full pipeline (PDF path → text files in output dir)
- preprocess: image preprocessing (binarization, deskew)
- postprocess: raw Tesseract text cleanup
- try_text_layer_page / run_layout_fallbacks / try_vector_tables: sparse layout and table hooks
"""

from .layout_strategies import run_layout_fallbacks, score_ocr_text, vertical_valley_column_bounds
from .pdf_tables_vector import extract_tables_camelot, extract_tables_tabula, try_vector_tables
from .pdf_text_layer import (
    TextLayerProbeResult,
    is_acceptable_text_layer,
    parse_use_text_layer_setting,
    probe_text_layer_policy,
    try_text_layer_page,
)
from .pipeline import ocr_pdf
from .preprocessor import preprocess
from .postprocessor import postprocess

__all__ = [
    "TextLayerProbeResult",
    "extract_tables_camelot",
    "extract_tables_tabula",
    "is_acceptable_text_layer",
    "ocr_pdf",
    "parse_use_text_layer_setting",
    "postprocess",
    "preprocess",
    "probe_text_layer_policy",
    "run_layout_fallbacks",
    "score_ocr_text",
    "try_text_layer_page",
    "try_vector_tables",
    "vertical_valley_column_bounds",
]
