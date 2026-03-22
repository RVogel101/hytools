"""OCR sub-package: PDF → image → Tesseract → postprocessed text.

Public API:
- ocr_pdf: full pipeline (PDF path → text files in output dir)
- preprocess: image preprocessing (binarization, deskew)
- postprocess: raw Tesseract text cleanup
"""

from .pipeline import ocr_pdf
from .preprocessor import preprocess
from .postprocessor import postprocess

__all__ = [
    "ocr_pdf",
    "preprocess",
    "postprocess",
]
