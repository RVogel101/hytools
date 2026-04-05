"""Per-page OCR metrics for MongoDB storage and downstream analysis.

Every page processed by :func:`ocr_pdf` produces one :class:`OCRPageMetric`
document.  Documents are stored in the ``ocr_page_metrics`` MongoDB
collection, keyed by ``(run_id, page_num)`` for efficient retrieval.

MongoDB Collection
------------------
**Name**: ``ocr_page_metrics``

**Indexes** (created by ``MongoDBCorpusClient._ensure_indexes``):

* ``(run_id, page_num)``  — unique compound; one record per page per run.
* ``(pdf_name, page_num)`` — fast lookup by filename.
* ``(status)``             — filter for failed/skipped pages.
* ``(timestamp)``          — chronological queries.
* ``(engine)``             — engine-level aggregation.

Schema Reference
----------------
Every document persisted to ``ocr_page_metrics`` conforms to the field
descriptions on :class:`OCRPageMetric`.  Key fields for analysis:

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Field
     - Type
     - Description / Usage
   * - ``run_id``
     - ``str``
     - UUID v4 grouping all pages from one ``ocr_pdf()`` invocation.
       Use to reconstruct a full PDF run or compare runs.
   * - ``pdf_path``
     - ``str``
     - Absolute path to the source PDF.
   * - ``pdf_name``
     - ``str``
     - Filename only (e.g. ``"textbook_ch3.pdf"``), for display.
   * - ``page_num``
     - ``int``
     - 1-based page number within the PDF.
   * - ``status``
     - ``str``
     - Outcome of the page: ``"success"`` | ``"text_layer"`` |
       ``"non_text"`` | ``"below_confidence"``.
   * - ``engine``
     - ``str``
     - Engine that produced the final text: ``"tesseract"`` |
       ``"surya"`` | ``"zone_ocr"`` | ``"text_layer"`` | ``"none"``.
   * - ``lang``
     - ``str``
     - Tesseract language string (``"hye"`` / ``"hye+eng"`` / ``"eng"``).
   * - ``mean_confidence``
     - ``float``
     - Mean Tesseract word-level confidence 0–100. ``-1`` when unavailable
       (text_layer, non_text).
   * - ``char_count``
     - ``int``
     - Characters in the final cleaned output text.
   * - ``word_count``
     - ``int``
     - Whitespace-delimited tokens in the final cleaned output text.
   * - ``dpi``
     - ``int``
     - DPI at which the page was rasterized.
   * - ``psm``
     - ``int``
     - Tesseract page-segmentation mode used.
   * - ``binarization``
     - ``str``
     - Binarization method: ``"sauvola"`` | ``"niblack"`` | ``"otsu"``.
   * - ``font_hint``
     - ``str | None``
     - Font-hint override (``"tiny"`` | ``"normal"`` | ``"cursive"``),
       or ``None`` if not set.
   * - ``adaptive_dpi``
     - ``bool``
     - Whether adaptive DPI resolution was active for this run.
   * - ``detect_cursive``
     - ``bool``
     - Whether cursive detection was enabled.
   * - ``page_type``
     - ``str | None``
     - Classifier label if ``classify_pages`` was active; ``None`` otherwise.
   * - ``classifier_confidence``
     - ``float | None``
     - Classifier confidence 0–1 if applicable.
   * - ``layout_fallback_used``
     - ``bool``
     - Whether layout-fallback strategies were attempted.
   * - ``zone_ocr_used``
     - ``bool``
     - Whether zone OCR was attempted for this page.
   * - ``vector_tables_appended``
     - ``bool``
     - Whether vector-table text was appended.
   * - ``confidence_threshold``
     - ``int``
     - The confidence gate configured for this run.
   * - ``attempts``
     - ``list[dict]``
     - Ordered list of :class:`OCRAttempt` records.  Each entry records
       one engine try with its score, confidence, and char count so the
       winning engine choice is fully traceable.
   * - ``timestamp``
     - ``datetime``
     - UTC time the record was created.

OCRAttempt Sub-document
-----------------------
Each element of the ``attempts`` array describes one engine try:

.. list-table::
   :header-rows: 1
   :widths: 18 10 72

   * - Field
     - Type
     - Description
   * - ``engine``
     - ``str``
     - ``"text_layer"`` | ``"tesseract"`` | ``"surya"`` |
       ``"zone_ocr"`` | ``"layout_fallback"``
   * - ``lang``
     - ``str | None``
     - Tesseract lang used (``None`` for text_layer/surya).
   * - ``psm``
     - ``int | None``
     - PSM used (``None`` when not applicable).
   * - ``score``
     - ``float``
     - ``score_ocr_text()`` result; ``-1`` when not scored.
   * - ``mean_confidence``
     - ``float``
     - Mean word-level Tesseract confidence; ``-1`` for non-Tesseract.
   * - ``char_count``
     - ``int``
     - Characters produced by this attempt.
   * - ``chosen``
     - ``bool``
     - ``True`` if this attempt produced the final output text.
   * - ``detail``
     - ``str | None``
     - Optional free-text note (e.g. layout strategy name).

Example Queries
---------------
.. code-block:: python

    # All pages with below-threshold confidence in a recent run
    db.ocr_page_metrics.find({"status": "below_confidence"}).sort("timestamp", -1)

    # Average confidence per engine across all runs
    db.ocr_page_metrics.aggregate([
        {"$match": {"status": "success"}},
        {"$group": {"_id": "$engine",
                     "avg_conf": {"$avg": "$mean_confidence"},
                     "pages": {"$sum": 1}}},
    ])

    # Pages where zone OCR was chosen over tesseract
    db.ocr_page_metrics.find({"engine": "zone_ocr"})

    # Per-PDF summary: total pages, mean confidence, word count
    db.ocr_page_metrics.aggregate([
        {"$group": {"_id": "$pdf_name",
                     "pages": {"$sum": 1},
                     "avg_conf": {"$avg": "$mean_confidence"},
                     "total_words": {"$sum": "$word_count"}}},
    ])

    # Pages where Surya beat Tesseract (look inside attempts)
    db.ocr_page_metrics.find({
        "attempts": {"$elemMatch": {"engine": "surya", "chosen": True}}
    })

    # Attempts breakdown per page for a specific run
    db.ocr_page_metrics.find(
        {"run_id": "<UUID>"},
        {"page_num": 1, "engine": 1, "attempts": 1}
    ).sort("page_num", 1)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OCRAttempt:
    """One engine try within a page's OCR processing.

    See *OCRAttempt Sub-document* in the module docstring for field details.
    """

    engine: str
    """``"text_layer"`` | ``"tesseract"`` | ``"surya"`` | ``"zone_ocr"`` | ``"layout_fallback"``"""
    lang: str | None = None
    """Tesseract lang used (``None`` for text_layer / surya)."""
    psm: int | None = None
    """PSM used (``None`` when not applicable)."""
    score: float = -1
    """``score_ocr_text()`` result; ``-1`` when not scored."""
    mean_confidence: float = -1
    """Mean word-level Tesseract confidence; ``-1`` for non-Tesseract."""
    char_count: int = 0
    """Characters produced by this attempt."""
    chosen: bool = False
    """``True`` if this attempt produced the final output text."""
    detail: str | None = None
    """Optional note (e.g. layout strategy name, rejection reason)."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OCRPageMetric:
    """One metric record per page processed by ``ocr_pdf()``.

    See *Schema Reference* in the module docstring for detailed field
    semantics and example MongoDB queries.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    run_id: str
    """UUID v4 grouping all pages from one ``ocr_pdf()`` call."""
    pdf_path: str
    """Absolute path to the source PDF."""
    pdf_name: str
    """Filename of the source PDF (no directory)."""
    page_num: int
    """1-based page number within the PDF."""

    # ── Outcome ───────────────────────────────────────────────────────────
    status: str
    """``"success"`` | ``"text_layer"`` | ``"non_text"`` | ``"below_confidence"``"""
    engine: str
    """``"tesseract"`` | ``"surya"`` | ``"zone_ocr"`` | ``"text_layer"`` | ``"none"``"""

    # ── Text metrics ──────────────────────────────────────────────────────
    mean_confidence: float
    """Mean Tesseract word-level confidence (0–100). ``-1`` when unavailable."""
    char_count: int
    """Characters in final cleaned text."""
    word_count: int
    """Whitespace-delimited tokens in final cleaned text."""

    # ── OCR parameters ────────────────────────────────────────────────────
    lang: str
    """Tesseract language string used for this page."""
    dpi: int
    """Rasterization DPI."""
    psm: int
    """Tesseract page-segmentation mode."""
    binarization: str
    """Binarization method (``"sauvola"`` | ``"niblack"`` | ``"otsu"``)."""

    # ── Run-level parameters ──────────────────────────────────────────────
    font_hint: str | None = None
    """``"tiny"`` | ``"normal"`` | ``"cursive"`` or ``None``."""
    adaptive_dpi: bool = False
    """Whether adaptive DPI resolution was active for this run."""
    detect_cursive: bool = False
    """Whether cursive detection was enabled."""

    # ── Classifier ────────────────────────────────────────────────────────
    page_type: str | None = None
    """Classifier label (``"pure_armenian"``, ``"mixed"``, etc.) or ``None``."""
    classifier_confidence: float | None = None
    """Classifier confidence 0–1, or ``None`` if classifier was not used."""

    # ── Strategy flags ────────────────────────────────────────────────────
    layout_fallback_used: bool = False
    """True if layout-fallback strategies were attempted."""
    zone_ocr_used: bool = False
    """True if zone OCR was attempted."""
    vector_tables_appended: bool = False
    """True if vector-table text was appended."""

    # ── Run context ───────────────────────────────────────────────────────
    confidence_threshold: int = 60
    """Confidence gate configured for this run."""

    # ── Attempt trail ─────────────────────────────────────────────────────
    attempts: list[OCRAttempt] = field(default_factory=list)
    """Ordered list of engine attempts with scores — full traceability."""

    timestamp: datetime = field(default_factory=_utcnow)
    """UTC time this record was created."""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for MongoDB ``insert_one``.

        ``OCRAttempt`` entries in *attempts* are expanded to plain dicts.
        """
        d = asdict(self)
        d["attempts"] = [a if isinstance(a, dict) else a for a in d.get("attempts", [])]
        return d


def new_run_id() -> str:
    """Generate a fresh UUID v4 run identifier."""
    return str(uuid.uuid4())


def write_page_metric(
    collection: Any,
    metric: OCRPageMetric,
) -> None:
    """Insert a single :class:`OCRPageMetric` into the MongoDB collection.

    Parameters
    ----------
    collection:
        A ``pymongo.collection.Collection`` (typically
        ``client.ocr_page_metrics``).
    metric:
        The populated metric dataclass.
    """
    try:
        collection.insert_one(metric.to_dict())
    except Exception as exc:
        logger.warning(
            "Failed to write OCR page metric (run=%s page=%d): %s",
            metric.run_id,
            metric.page_num,
            exc,
        )
