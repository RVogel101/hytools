"""Hybrid OCR: OCRmyPDF and Kraken engines as optional best-of contenders.

OCRmyPDF wraps Tesseract with superior PDF handling (hOCR → PDF/A), while
Kraken is a deep-learning-first OCR engine with excellent support for
non-Latin scripts including Armenian.  Both are optional dependencies;
the module lazy-loads so ``import hytools.ocr`` never fails.

Install (optional)::

    pip install ocrmypdf     # OCRmyPDF (wraps Tesseract under the hood)
    pip install kraken        # Kraken OCR engine

Both engines produce text that competes on ``score_ocr_text()`` alongside
Tesseract, Surya, zone-OCR, and classical-OCR in the pipeline.

Configuration
~~~~~~~~~~~~~
.. code-block:: yaml

    ocr:
      use_ocrmypdf: auto       # true | false | "auto"
      use_kraken: auto         # true | false | "auto"
      kraken_model: ""         # path or name of Kraken model (default: built-in)
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

# ── OCRmyPDF ─────────────────────────────────────────────────────────────────

_ocrmypdf_available: bool | None = None


def is_ocrmypdf_available() -> bool:
    """Return True if ``ocrmypdf`` is importable."""
    global _ocrmypdf_available
    if _ocrmypdf_available is None:
        try:
            import ocrmypdf  # noqa: F401
            _ocrmypdf_available = True
        except Exception:
            logger.debug("ocrmypdf not available")
            _ocrmypdf_available = False
    return _ocrmypdf_available


def ocrmypdf_page(
    pil_image: Image.Image,
    lang: str = "hye+eng",
    dpi: int = 300,
) -> str | None:
    """Run OCRmyPDF on a single page image and return extracted text.

    OCRmyPDF operates on PDF files, so we convert the image to a
    single-page PDF, run OCR, then extract the text layer.

    Returns *None* if OCRmyPDF is unavailable or the attempt fails.
    """
    if not is_ocrmypdf_available():
        return None

    try:
        import ocrmypdf
        import pikepdf

        with tempfile.TemporaryDirectory() as tmpdir:
            in_pdf = Path(tmpdir) / "input.pdf"
            out_pdf = Path(tmpdir) / "output.pdf"

            # Save image as single-page PDF
            pil_image.save(str(in_pdf), "PDF", resolution=dpi)

            # Run OCRmyPDF
            ocrmypdf.ocr(
                str(in_pdf),
                str(out_pdf),
                language=lang.replace("+", "+"),
                deskew=False,  # we handle preprocessing ourselves
                force_ocr=True,
                progress_bar=False,
            )

            # Extract text from the OCR'd PDF
            with pikepdf.open(out_pdf) as pdf:
                text_parts: list[str] = []
                for page in pdf.pages:
                    # Use pikepdf to extract text
                    text_parts.append(page.extract_text() if hasattr(page, "extract_text") else "")

                text = "\n".join(text_parts)

            return text if text.strip() else None
    except Exception as exc:
        logger.warning("OCRmyPDF attempt failed: %s", exc)
        return None


# ── Kraken ────────────────────────────────────────────────────────────────────

_kraken_available: bool | None = None
_kraken_model: Any = None


def is_kraken_available() -> bool:
    """Return True if ``kraken`` is importable."""
    global _kraken_available
    if _kraken_available is None:
        try:
            import kraken  # noqa: F401
            _kraken_available = True
        except Exception:
            logger.debug("kraken not available")
            _kraken_available = False
    return _kraken_available


def _ensure_kraken_model(model_path: str = "") -> bool:
    """Load the Kraken recognition model once.  Returns True on success."""
    global _kraken_model

    if _kraken_model is not None:
        return True

    if not is_kraken_available():
        return False

    try:
        from kraken.lib import models as kraken_models

        if model_path:
            _kraken_model = kraken_models.load_any(model_path)
        else:
            # Use Kraken's default built-in model
            _kraken_model = kraken_models.load_any("en_best.mlmodel")
        logger.info("Kraken model loaded: %s", model_path or "default")
        return True
    except Exception as exc:
        logger.warning("Failed to load Kraken model: %s", exc)
        _kraken_available = False
        return False


def kraken_ocr_image(
    pil_image: Image.Image,
    model_path: str = "",
) -> str | None:
    """Run Kraken OCR on *pil_image* and return the recognized text.

    Returns *None* if Kraken is unavailable or recognition fails.
    """
    if not _ensure_kraken_model(model_path):
        return None

    try:
        from kraken import binarization as kraken_binarize
        from kraken import rpred, segmentation

        # Binarize the image (Kraken's own preprocessing)
        bw = kraken_binarize.nlbin(pil_image)

        # Segment the page into lines
        seg_result = segmentation.segment(bw)

        # Recognize each line
        pred_iter = rpred.rpred(_kraken_model, bw, seg_result)
        lines = [record.prediction for record in pred_iter]

        text = "\n".join(lines)
        return text if text.strip() else None
    except Exception as exc:
        logger.warning("Kraken OCR attempt failed: %s", exc)
        return None


# ── Reset (testing) ──────────────────────────────────────────────────────────

def reset() -> None:
    """Reset cached availability flags (useful for testing)."""
    global _ocrmypdf_available, _kraken_available, _kraken_model
    _ocrmypdf_available = None
    _kraken_available = None
    _kraken_model = None
