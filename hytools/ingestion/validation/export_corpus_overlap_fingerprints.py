"""Detect near-duplicate documents using normalized content hashes.

Scans the ``documents`` collection for entries sharing the same
``normalized_content_hash`` (NFKC-normalized SHA-256) but originating from
different sources.  This catches near-duplicates that differ only in
whitespace or Unicode normalization.

Results are stored as a report in the ``metadata`` collection.
No separate ``fingerprints`` collection is maintained — all hashing
lives on the document itself (``content_hash`` for exact dedup,
``normalized_content_hash`` for fuzzy dedup).
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_DOCS = 50_000


def _normalize_and_hash(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _backfill_normalized_hashes(docs_col) -> int:
    """Compute normalized_content_hash for documents that lack it."""
    missing = docs_col.find(
        {"normalized_content_hash": {"$exists": False}, "text": {"$exists": True, "$ne": ""}},
        {"text": 1},
    )
    backfilled = 0
    for doc in missing:
        nhash = _normalize_and_hash(doc.get("text", ""))
        docs_col.update_one({"_id": doc["_id"]}, {"$set": {"normalized_content_hash": nhash}})
        backfilled += 1
    return backfilled


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for fingerprint analysis")

        docs = client.documents
        total = docs.count_documents({})

        backfilled = _backfill_normalized_hashes(docs)
        if backfilled:
            logger.info("Backfilled normalized_content_hash on %d documents", backfilled)

        pipeline: list[dict[str, Any]] = [
            {"$match": {"normalized_content_hash": {"$exists": True}}},
            {"$group": {
                "_id": "$normalized_content_hash",
                "count": {"$sum": 1},
                "sources": {"$addToSet": "$source"},
                "titles": {"$push": "$title"},
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 500},
        ]

        duplicates = list(docs.aggregate(pipeline))

        cross_source = [d for d in duplicates if len(d["sources"]) > 1]
        same_source = [d for d in duplicates if len(d["sources"]) == 1]

        source_pipeline: list[dict[str, Any]] = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        source_counts = {r["_id"]: r["count"] for r in docs.aggregate(source_pipeline)}

        summary: dict[str, Any] = {
            "stage": "export_corpus_overlap_fingerprints",
            "timestamp": datetime.now(timezone.utc),
            "total_documents": total,
            "backfilled_hashes": backfilled,
            "near_duplicate_groups": len(duplicates),
            "cross_source_duplicates": len(cross_source),
            "same_source_duplicates": len(same_source),
            "top_cross_source": [
                {
                    "hash": d["_id"][:16] + "...",
                    "count": d["count"],
                    "sources": d["sources"],
                    "sample_titles": d["titles"][:3],
                }
                for d in cross_source[:20]
            ],
            "source_counts": source_counts,
        }

        client.metadata.replace_one(
            {"stage": "export_corpus_overlap_fingerprints"},
            summary,
            upsert=True,
        )

        logger.info(
            "Fingerprint analysis: %d near-dup groups (%d cross-source, %d same-source)",
            len(duplicates), len(cross_source), len(same_source),
        )
        print(f"Documents: {total}")
        print(f"Near-duplicate groups: {len(duplicates)}")
        print(f"  Cross-source: {len(cross_source)}")
        print(f"  Same-source: {len(same_source)}")
        if cross_source:
            print("Top cross-source duplicates:")
            for d in cross_source[:5]:
                print(f"  {d['count']}x across {d['sources']}: {d['titles'][:2]}")
        print(f"Sources: {source_counts}")


def _load_config(config_path: str | None) -> dict:
    if not config_path:
        return {}
    from pathlib import Path
    p = Path(config_path)
    if not p.exists():
        return {}
    import yaml
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Detect near-duplicate documents via normalized content hashes")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML config (database.*)")
    args = parser.parse_args()
    config = _load_config(args.config)
    try:
        run(config)
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
