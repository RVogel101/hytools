#!/usr/bin/env python3
"""Summarize corpus documents in MongoDB by source and dialect."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for summarization")

        docs = client.documents

        total = docs.count_documents({})
        non_empty = docs.count_documents({"text": {"$exists": True, "$ne": ""}})
        with_hash = docs.count_documents({"content_hash": {"$exists": True, "$ne": ""}})

        source_pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        by_source = {r["_id"]: r["count"] for r in docs.aggregate(source_pipeline)}

        dialect_pipeline = [
            {"$group": {"_id": "$dialect_view", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        by_dialect = {str(r["_id"]): r["count"] for r in docs.aggregate(dialect_pipeline)}

        char_pipeline = [
            {"$match": {"metadata.char_count": {"$exists": True}}},
            {"$group": {
                "_id": None,
                "total_chars": {"$sum": "$metadata.char_count"},
                "total_words": {"$sum": "$metadata.word_count"},
            }},
        ]
        size_stats = list(docs.aggregate(char_pipeline))
        total_chars = size_stats[0]["total_chars"] if size_stats else 0
        total_words = size_stats[0]["total_words"] if size_stats else 0

        summary = {
            "stage": "summarize_unified_documents",
            "timestamp": datetime.now(timezone.utc),
            "total_records": total,
            "non_empty_text": non_empty,
            "empty_text": total - non_empty,
            "with_content_hash": with_hash,
            "total_characters": total_chars,
            "total_words": total_words,
            "by_source": by_source,
            "by_dialect_view": by_dialect,
        }

        client.metadata.replace_one(
            {"stage": "summarize_unified_documents"},
            summary,
            upsert=True,
        )

        print(f"Corpus summary: {total} documents ({non_empty} with text)")
        print(f"  Characters: {total_chars:,}  Words: {total_words:,}")
        print(f"  Sources: {by_source}")
        print(f"  Dialects: {by_dialect}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run({})
