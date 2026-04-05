"""MongoDB-native cleaning: normalize and filter corpus documents in place.

Reads from MongoDB documents collection, normalizes text, runs Western Armenian
filter, computes internal_language_branch from dialect classifier, and updates
processing flags. No file I/O. Deduplication is deferred (requires batch MinHash
over corpus).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _classify_branch(wa_score: float, text: str) -> str:
    """Determine internal_language_branch from WA score and text analysis.

    Returns one of 'hye-w', 'hye-e', or 'eng'.
    """
    from hytools.cleaning.language_filter import _has_armenian_script
    if not _has_armenian_script(text):
        return "eng"
    if wa_score >= 5.0:
        return "hye-w"
    return "hye-e"


def run(config: dict) -> None:
    """Normalize and filter MongoDB corpus documents in place."""
    try:
        from hytools.ingestion._shared.helpers import open_mongodb_client
        from hytools.linguistics.dialect.branch_dialect_classifier import (
            compute_wa_score,
            WA_SCORE_THRESHOLD,
        )
    except ImportError:
        logger.error("required helpers not available")
        raise

    from .normalizer import normalize

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB required but unavailable")

        coll = client.db["documents"]
        cursor = coll.find({"text": {"$exists": True, "$ne": ""}})
        updated = 0
        filtered_count = 0
        for doc in cursor:
            doc_id = doc["_id"]
            text = doc.get("text", "")
            if not text:
                continue

            normalized_text = normalize(text)
            wa_score = compute_wa_score(normalized_text)
            is_wa = wa_score >= WA_SCORE_THRESHOLD
            branch = _classify_branch(wa_score, normalized_text)

            coll.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "text": normalized_text,
                        "processing.normalized": True,
                        "processing.filtered": is_wa,
                        "processing.internal_language_classified": True,
                        "metadata.wa_score": wa_score,
                        "metadata.internal_language_branch": branch,
                    }
                },
            )
            updated += 1
            if is_wa:
                filtered_count += 1
            if updated % 1000 == 0:
                logger.info("Cleaning MongoDB: %d updated, %d WA", updated, filtered_count)

        logger.info("MongoDB cleaning complete: %d normalized, %d Western Armenian", updated, filtered_count)


def migrate_dialect_field(config: dict) -> dict:
    """Backfill metadata.internal_language_branch for documents missing it.

    For documents that already have metadata.wa_score but lack
    internal_language_branch, derives the branch from the existing score.
    For documents without wa_score, computes it from text.

    Returns summary dict with counts.
    """
    try:
        from hytools.ingestion._shared.helpers import open_mongodb_client
        from hytools.linguistics.dialect.branch_dialect_classifier import (
            compute_wa_score,
        )
    except ImportError:
        logger.error("required helpers not available")
        raise

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB required but unavailable")

        coll = client.db["documents"]

        # Phase 1: Documents with wa_score but no internal_language_branch
        cursor_scored = coll.find({
            "metadata.wa_score": {"$exists": True},
            "metadata.internal_language_branch": {"$exists": False},
            "text": {"$exists": True, "$ne": ""},
        })
        migrated_from_score = 0
        for doc in cursor_scored:
            wa_score = doc.get("metadata", {}).get("wa_score", 0.0)
            text = doc.get("text", "")
            branch = _classify_branch(wa_score, text)
            coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "metadata.internal_language_branch": branch,
                    "processing.internal_language_classified": True,
                }},
            )
            migrated_from_score += 1

        # Phase 2: Documents with neither wa_score nor internal_language_branch
        cursor_unscored = coll.find({
            "metadata.wa_score": {"$exists": False},
            "metadata.internal_language_branch": {"$exists": False},
            "text": {"$exists": True, "$ne": ""},
        })
        migrated_from_text = 0
        for doc in cursor_unscored:
            text = doc.get("text", "")
            if not text:
                continue
            wa_score = compute_wa_score(text)
            branch = _classify_branch(wa_score, text)
            coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "metadata.wa_score": wa_score,
                    "metadata.internal_language_branch": branch,
                    "processing.internal_language_classified": True,
                }},
            )
            migrated_from_text += 1

        total = migrated_from_score + migrated_from_text
        logger.info(
            "Dialect migration: %d total (%d from existing score, %d from text analysis)",
            total, migrated_from_score, migrated_from_text,
        )
        return {
            "migrated_from_score": migrated_from_score,
            "migrated_from_text": migrated_from_text,
            "total": total,
        }
