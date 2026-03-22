"""Annotate Anki `cards` collection with frequency/difficulty/composite metadata.

Usage:
    python 07-tools/annotate_anki_with_frequency.py

This reads `word_frequencies` collection and updates matching cards in `cards` collection
by setting: `frequency_rank`, `frequency_total`, `difficulty`, `phonetic_score`,
`orthographic_score`, `composite_score`, and `used_aggregate`.
"""
from __future__ import annotations

from hytool.ingestion._shared.helpers import open_mongodb_client
import logging

logger = logging.getLogger(__name__)


def run(cfg: dict | None = None) -> None:
    cfg = cfg or {}
    with open_mongodb_client(cfg) as client:
        if client is None:
            raise RuntimeError("MongoDB client required")
        db = client.db
        freq_col = db.get_collection("word_frequencies")
        cards_col = db.get_collection("cards")

        cursor = freq_col.find({}, {"word": 1, "rank": 1, "total_count": 1, "difficulty": 1, "phonetic_score": 1, "orthographic_score": 1, "composite_score": 1, "used_aggregate": 1})
        updated = 0
        for doc in cursor:
            word = doc.get("word")
            if not word:
                continue
            update = {
                "$set": {
                    "frequency_rank": doc.get("rank"),
                    "frequency_total": doc.get("total_count"),
                    "difficulty": doc.get("difficulty"),
                    "phonetic_score": doc.get("phonetic_score"),
                    "orthographic_score": doc.get("orthographic_score"),
                    "composite_score": doc.get("composite_score"),
                    "used_aggregate": doc.get("used_aggregate"),
                }
            }

            # Primary: update by exact word field
            res = cards_col.update_many({"word": word}, update)
            modified = res.modified_count if hasattr(res, 'modified_count') else 0

            # If no cards matched, try common Anki field names (front/back/fields)
            if modified == 0:
                # try front/back text fields
                res2 = cards_col.update_many({"front": word}, update)
                modified = (res2.modified_count if hasattr(res2, 'modified_count') else 0)
            if modified == 0:
                res3 = cards_col.update_many({"fields.0": word}, update)
                modified = (res3.modified_count if hasattr(res3, 'modified_count') else 0)

            if modified:
                updated += modified
        logger.info("Annotated %d card documents with frequency metadata", updated)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

