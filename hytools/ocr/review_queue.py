"""Backward-compatible OCR review queue exports.

The implementation now lives in ``hytools.ingestion._shared.review_queue`` so
acquisition and OCR stages share a single review queue schema and helpers.
"""

from hytools.ingestion._shared.review_queue import (  # noqa: F401
    PRIORITY_BELOW_CONFIDENCE,
    PRIORITY_BORDERLINE_CRAWLER,
    PRIORITY_BORDERLINE_DIALECT,
    PRIORITY_EMPTY_FALLBACK,
    PRIORITY_NON_TEXT,
    PRIORITY_OCR_ERROR,
    PRIORITY_SOURCE_POLICY,
    ReviewItem,
    build_review_run_id,
    classification_detail,
    enqueue_for_review,
    get_review_collection,
    make_thumbnail,
    maybe_enqueue_language_review,
    should_enqueue_low_confidence_classification,
)

__all__ = [
    "PRIORITY_BELOW_CONFIDENCE",
    "PRIORITY_BORDERLINE_CRAWLER",
    "PRIORITY_BORDERLINE_DIALECT",
    "PRIORITY_EMPTY_FALLBACK",
    "PRIORITY_NON_TEXT",
    "PRIORITY_OCR_ERROR",
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
