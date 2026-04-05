"""Optional Surya OCR engine: deep-learning-based text detection + recognition.

Surya (https://github.com/VikParuchuri/surya) runs 100 % locally — models are
downloaded from HuggingFace on first use, after which no network access is needed.
It benchmarks at 0.97 avg similarity vs Tesseract's 0.88 across 90+ languages
including Armenian.

Install::

    pip install surya-ocr          # requires Python 3.10+ and PyTorch

The module lazy-loads Surya so ``import hytools.ocr`` never fails when Surya is
not installed. All public functions return ``None`` when Surya is unavailable.

GPU tips (set env vars before importing):

    RECOGNITION_BATCH_SIZE  — default 512 (GPU) / 32 (CPU); each item ≈ 40 MB VRAM
    DETECTOR_BATCH_SIZE     — default 36 (GPU) / 6 (CPU); each item ≈ 440 MB VRAM
    TORCH_DEVICE            — "cuda", "cpu", etc.  Auto-detected by default.
"""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singletons — heavy models are loaded once and reused.
# ---------------------------------------------------------------------------

_foundation_predictor: Any = None
_detection_predictor: Any = None
_recognition_predictor: Any = None
_available: bool | None = None  # tri-state: None = not checked yet


def is_surya_available() -> bool:
    """Return True if ``surya-ocr`` is importable."""
    global _available
    if _available is None:
        try:
            import surya.recognition  # noqa: F401
            import surya.detection  # noqa: F401
            _available = True
        except Exception:
            logger.debug("surya-ocr not available")
            _available = False
    return _available


def _ensure_predictors() -> bool:
    """Load Surya predictors (once). Returns True on success."""
    global _foundation_predictor, _detection_predictor, _recognition_predictor

    if _recognition_predictor is not None:
        return True

    if not is_surya_available():
        return False

    try:
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor

        _foundation_predictor = FoundationPredictor()
        _recognition_predictor = RecognitionPredictor(_foundation_predictor)
        _detection_predictor = DetectionPredictor()
        logger.info("Surya OCR predictors loaded successfully")
        return True
    except Exception as exc:
        logger.warning("Failed to initialise Surya predictors: %s", exc)
        _available = False
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def surya_ocr_image(image: Image.Image) -> str | None:
    """Run Surya OCR on a single PIL image and return the full page text.

    Returns ``None`` if Surya is not installed or OCR fails.  Lines are
    joined with newlines in reading order (top-to-bottom, left-to-right).
    """
    if not _ensure_predictors():
        return None

    try:
        # Surya expects a list of images; returns a list of page results.
        predictions = _recognition_predictor(
            [image],
            det_predictor=_detection_predictor,
        )
        if not predictions:
            return None

        page = predictions[0]

        # Extract text lines from the prediction result.
        # The structure depends on Surya version:
        #   v0.17+:  page is a dict with "text_lines" list
        #   earlier: page may be an object with .text_lines attribute
        text_lines = _extract_text_lines(page)
        if not text_lines:
            return None

        return "\n".join(text_lines)
    except Exception as exc:
        logger.debug("Surya OCR failed: %s", exc)
        return None


def surya_ocr_image_with_confidence(
    image: Image.Image,
) -> tuple[str | None, float]:
    """Run Surya OCR and return ``(text, mean_confidence)``.

    Confidence is the mean of per-line confidence scores (0–1 scale).
    Returns ``(None, 0.0)`` on failure.
    """
    if not _ensure_predictors():
        return None, 0.0

    try:
        predictions = _recognition_predictor(
            [image],
            det_predictor=_detection_predictor,
        )
        if not predictions:
            return None, 0.0

        page = predictions[0]
        lines_data = _extract_lines_data(page)
        if not lines_data:
            return None, 0.0

        texts: list[str] = []
        confidences: list[float] = []
        for ld in lines_data:
            t = ld.get("text", "")
            if t:
                texts.append(t)
            c = ld.get("confidence", 0.0)
            if isinstance(c, (int, float)):
                confidences.append(float(c))

        text = "\n".join(texts) if texts else None
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return text, mean_conf
    except Exception as exc:
        logger.debug("Surya OCR with confidence failed: %s", exc)
        return None, 0.0


# ---------------------------------------------------------------------------
# Internal helpers — cope with Surya API variations across versions.
# ---------------------------------------------------------------------------


def _extract_lines_data(page: Any) -> list[dict]:
    """Return a list of ``{"text": ..., "confidence": ...}`` dicts from a
    Surya page prediction, handling both dict and object formats."""
    # Dict format (v0.17+)
    if isinstance(page, dict):
        return page.get("text_lines", [])

    # Object format (earlier versions)
    if hasattr(page, "text_lines"):
        raw = page.text_lines
        if isinstance(raw, list):
            out: list[dict] = []
            for item in raw:
                if isinstance(item, dict):
                    out.append(item)
                elif hasattr(item, "text"):
                    out.append({
                        "text": getattr(item, "text", ""),
                        "confidence": getattr(item, "confidence", 0.0),
                    })
            return out

    return []


def _extract_text_lines(page: Any) -> list[str]:
    """Return plain text strings from a Surya page prediction."""
    lines_data = _extract_lines_data(page)
    return [d["text"] for d in lines_data if d.get("text")]
