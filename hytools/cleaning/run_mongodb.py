"""MongoDB-native cleaning: normalize and filter corpus documents in place.

Reads from MongoDB documents collection, normalizes text, runs Western Armenian
filter, and updates processing flags. No file I/O. Deduplication is deferred
(requires batch MinHash over corpus).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """Normalize and filter MongoDB corpus documents in place."""
    try:
        from hytools.ingestion._shared.helpers import open_mongodb_client, compute_wa_score, WA_SCORE_THRESHOLD
    except ImportError:
        logger.error("ingestion._shared.helpers not available")
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

            coll.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "text": normalized_text,
                        "processing.normalized": True,
                        "processing.filtered": is_wa,
                        "processing.internal_language_classified": True,
                        "metadata.wa_score": wa_score,
                    }
                },
            )
            updated += 1
            if is_wa:
                filtered_count += 1
            if updated % 1000 == 0:
                logger.info("Cleaning MongoDB: %d updated, %d WA", updated, filtered_count)

        logger.info("MongoDB cleaning complete: %d normalized, %d Western Armenian", updated, filtered_count)
