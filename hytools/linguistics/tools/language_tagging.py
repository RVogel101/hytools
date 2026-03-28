"""Produce internal language tags from text using existing dialect classifier.

This module provides a single entry-point `classify_text_to_internal_tags`
which returns `(internal_language_code, internal_language_branch)` when the
classifier produces a confident Western/Eastern label. If the classifier is
inconclusive or identifies classical text, this function returns `(None, None)`
— callers must treat both fields as absent in that case.

This intentionally does NOT provide fallbacks or shims; it maps only when the
underlying classifier yields a clear likely_western or likely_eastern label.
"""

from __future__ import annotations

from typing import Tuple, Dict, Any

from ...ingestion._shared.helpers import classify_text_classification, normalize_internal_language_branch


def classify_text_to_internal_tags(text: str) -> Tuple[str | None, str | None]:
    """Classify a text and return internal tags (backwards compatible).

    Uses `classify_text_classification` under the hood but preserves the
    original two-tuple return shape for callers that expect it.
    """
    result = classify_text_classification(text)
    label = result.get("label")

    if label == "likely_western":
        return "hyw", normalize_internal_language_branch("hye-w")
    if label == "likely_eastern":
        return "hye", normalize_internal_language_branch("hye-e")

    return None, None


def classify_text_to_internal_tags_detailed(text: str) -> Dict[str, Any]:
    """Return detailed classification including evidence and confidence.

    Returns a dict with keys: `internal_language_code`, `internal_language_branch`,
    `label`, `confidence`, `western_score`, `eastern_score`, `classical_score`,
    and `evidence` (list of EvidenceHit dicts).
    """
    result = classify_text_classification(text)
    label = result.get("label")
    code = None
    branch = None
    if label == "likely_western":
        code = "hyw"
        branch = normalize_internal_language_branch("hye-w")
    elif label == "likely_eastern":
        code = "hye"
        branch = normalize_internal_language_branch("hye-e")

    return {
        "internal_language_code": code,
        "internal_language_branch": branch,
        "label": label,
        "confidence": result.get("confidence"),
        "western_score": result.get("western_score"),
        "eastern_score": result.get("eastern_score"),
        "classical_score": result.get("classical_score"),
        "evidence": result.get("evidence"),
        "text": result.get("text"),
    }


__all__ = ["classify_text_to_internal_tags"]
