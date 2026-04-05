"""Unified manual review queue helpers shared by OCR and ingestion stages.

The physical MongoDB collection remains ``ocr_review_queue`` for backward
compatibility, but the schema now supports non-OCR review items as well.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from PIL import Image

from hytools.linguistics.dialect.branch_dialect_classifier import classify_text_classification
from hytools.linguistics.dialect.review_audit import get_review_priority, get_stage_review_settings

logger = logging.getLogger(__name__)

_THUMBNAIL_MAX_PX = 512
_JPEG_QUALITY = 72
_ARMENIAN_CHAR_RE = re.compile(r"[\u0531-\u0587]")
_RUN_ID_SANITIZE_RE = re.compile(r"[^0-9A-Za-z._:-]+")

# Priority mapping: lower = more urgent
PRIORITY_BELOW_CONFIDENCE = 1
PRIORITY_EMPTY_FALLBACK = 2
PRIORITY_NON_TEXT = 3
PRIORITY_OCR_ERROR = 2
PRIORITY_BORDERLINE_DIALECT = get_review_priority("low_confidence_dialect_classification", 1)
PRIORITY_BORDERLINE_CRAWLER = get_review_priority("borderline_crawl_page", 2)
PRIORITY_SOURCE_POLICY = get_review_priority("source_policy_exception", 2)
_REVIEW_DEFAULTS = get_stage_review_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_thumbnail(pil_image: Image.Image, max_px: int = _THUMBNAIL_MAX_PX) -> bytes:
    """Downscale a PIL image and return JPEG bytes."""
    img = pil_image.copy()
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    return buf.getvalue()


def build_review_run_id(queue_source: str, stage: str, item_id: str, reason: str) -> str:
    """Build a stable synthetic run id for non-OCR review items."""
    raw = ":".join(part for part in (queue_source, stage, item_id, reason) if part)
    sanitized = _RUN_ID_SANITIZE_RE.sub("_", raw).strip("_")
    return sanitized or "review_item"


def classification_detail(result: dict[str, Any]) -> str:
    """Render a compact classifier summary for review queue details."""
    return (
        f"label={result.get('label', 'inconclusive')} "
        f"confidence={float(result.get('confidence', 0.0) or 0.0):.3f} "
        f"western={float(result.get('western_score', 0.0) or 0.0):.3f} "
        f"eastern={float(result.get('eastern_score', 0.0) or 0.0):.3f} "
        f"classical={float(result.get('classical_score', 0.0) or 0.0):.3f}"
    )


def should_enqueue_low_confidence_classification(
    result: dict[str, Any],
    *,
    confidence_threshold: float | None = None,
    score_margin_threshold: float | None = None,
) -> bool:
    """Return True when a dialect classification is too ambiguous to trust."""
    if confidence_threshold is None:
        confidence_threshold = float(_REVIEW_DEFAULTS.get("confidence_threshold", 0.35) or 0.35)
    if score_margin_threshold is None:
        score_margin_threshold = float(_REVIEW_DEFAULTS.get("score_margin_threshold", 2.0) or 2.0)

    western = float(result.get("western_score", 0.0) or 0.0)
    eastern = float(result.get("eastern_score", 0.0) or 0.0)
    classical = float(result.get("classical_score", 0.0) or 0.0)
    confidence = float(result.get("confidence", 0.0) or 0.0)
    label = str(result.get("label", "inconclusive") or "inconclusive")
    if western <= 0.0 and eastern <= 0.0 and classical <= 0.0:
        return False
    if label == "inconclusive":
        return True
    if confidence < confidence_threshold:
        return True
    return abs(western - eastern) < score_margin_threshold


def get_review_collection(client: Any) -> Any | None:
    """Resolve the shared review queue collection from a MongoDB client."""
    if client is None:
        return None
    try:
        collection = getattr(client, "review_queue", None)
        if collection is not None:
            return collection
    except Exception:
        logger.debug("Unified review queue property unavailable", exc_info=True)
    try:
        return getattr(client, "ocr_review_queue", None)
    except Exception:
        logger.debug("Legacy OCR review queue property unavailable", exc_info=True)
        return None


@dataclass
class ReviewItem:
    """One entry in the manual review queue."""

    run_id: str = ""
    pdf_path: str = ""
    pdf_name: str = ""
    page_num: int = 0

    reason: str = ""
    priority: int = PRIORITY_EMPTY_FALLBACK
    detail: str = ""

    mean_confidence: float = -1
    lang: str = ""
    dpi: int = 300
    thumbnail: bytes = b""

    queue_source: str = "ocr"
    stage: str = ""
    item_id: str = ""
    title: str = ""
    source_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    reviewed: bool = False
    reviewer_notes: str = ""
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for MongoDB ``insert_one``."""
        data = asdict(self)
        data["run_id"] = data["run_id"] or build_review_run_id(
            data.get("queue_source", "review"),
            data.get("stage", ""),
            data.get("item_id", data.get("pdf_name", "")),
            data.get("reason", "review"),
        )
        if not data.get("pdf_name"):
            data["pdf_name"] = data.get("title") or data.get("item_id") or data["run_id"]
        return data


def enqueue_for_review(collection: Any, item: ReviewItem) -> None:
    """Insert a :class:`ReviewItem` into the review queue collection."""
    try:
        payload = item.to_dict()
        collection.insert_one(payload)
        display_name = payload.get("pdf_name") or payload.get("title") or payload.get("item_id") or payload["run_id"]
        logger.info(
            "Review queue: flagged %s (%s, priority=%d, stage=%s)",
            display_name,
            payload.get("reason", "review"),
            int(payload.get("priority", PRIORITY_EMPTY_FALLBACK)),
            payload.get("stage", ""),
        )
    except Exception as exc:
        logger.warning(
            "Failed to enqueue review item (%s / %s): %s",
            item.stage or item.queue_source,
            item.item_id or item.pdf_name,
            exc,
        )


def maybe_enqueue_language_review(
    collection: Any,
    *,
    stage: str,
    item_id: str,
    text: str,
    title: str = "",
    source_url: str = "",
    queue_source: str = "ingestion",
    rejected: bool = False,
    confidence_threshold: float | None = None,
    score_margin_threshold: float | None = None,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """Queue low-confidence or policy-rejected text classification decisions."""
    if collection is None:
        return None

    if confidence_threshold is None:
        confidence_threshold = float(_REVIEW_DEFAULTS.get("confidence_threshold", 0.35) or 0.35)
    if score_margin_threshold is None:
        score_margin_threshold = float(_REVIEW_DEFAULTS.get("score_margin_threshold", 2.0) or 2.0)

    sample = (text or "")[:12000]
    if not sample.strip() or not _ARMENIAN_CHAR_RE.search(sample):
        return None

    classification = classify_text_classification(sample)
    label = str(classification.get("label", "inconclusive") or "inconclusive")

    reason: str | None = None
    priority = PRIORITY_BORDERLINE_DIALECT
    if rejected and label == "likely_eastern":
        reason = "source_policy_exception"
        priority = PRIORITY_SOURCE_POLICY
    elif should_enqueue_low_confidence_classification(
        classification,
        confidence_threshold=confidence_threshold,
        score_margin_threshold=score_margin_threshold,
    ):
        reason = "low_confidence_dialect_classification"
        priority = PRIORITY_BORDERLINE_DIALECT

    if reason is None:
        return None

    enqueue_for_review(
        collection,
        ReviewItem(
            run_id=build_review_run_id(queue_source, stage, item_id, reason),
            pdf_path=source_url,
            pdf_name=title or item_id,
            page_num=0,
            reason=reason,
            priority=priority,
            detail=classification_detail(classification),
            queue_source=queue_source,
            stage=stage,
            item_id=item_id,
            title=title,
            source_url=source_url,
            extra={**(extra or {}), "classification": classification},
        ),
    )
    return reason


__all__ = [
    "PRIORITY_BELOW_CONFIDENCE",
    "PRIORITY_EMPTY_FALLBACK",
    "PRIORITY_NON_TEXT",
    "PRIORITY_OCR_ERROR",
    "PRIORITY_BORDERLINE_DIALECT",
    "PRIORITY_BORDERLINE_CRAWLER",
    "PRIORITY_SOURCE_POLICY",
    "ReviewItem",
    "build_review_run_id",
    "classification_detail",
    "enqueue_for_review",
    "get_review_collection",
    "make_thumbnail",
    "maybe_enqueue_language_review",
    "should_enqueue_low_confidence_classification",
]