#!/usr/bin/env python3
"""Materialize dialect-specific views from MongoDB corpus.

Tags each document with a canonical ``dialect_view`` field based on the
text-derived ``internal_language_branch`` metadata (preferred) or the
source-provided ``source_language_code`` (fallback), enabling fast filtered
queries for WA-only training datasets, EA reference data, etc.

Also stores dialect distribution stats in the ``metadata`` collection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# internal_language_branch → dialect_view tag  (primary — text-derived)
_BRANCH_TO_VIEW = {
    "hye-w": "wa",
    "hye-e": "ea",
    "eng": "eng",
}

# source_language_code → dialect_view tag  (fallback — source-declared)
_SOURCE_LANG_TO_VIEW = {
    "hyw": "wa",
    "hye": "ea",
    "hy": "ea",     # legacy undetermined Armenian → treat as EA for safety
    "hyc": "ea",    # Classical Armenian
    "en": "eng",
}


def run(config: dict) -> None:
    from ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for dialect materialization")

        docs = client.documents
        docs.create_index("dialect_view")

        total = docs.count_documents({})
        stats: dict[str, int] = {"wa": 0, "ea": 0, "eng": 0, "unknown": 0}

        # Primary: classify by internal_language_branch (text-derived)
        for branch, view_tag in _BRANCH_TO_VIEW.items():
            count = docs.update_many(
                {"metadata.internal_language_branch": branch},
                {"$set": {"dialect_view": view_tag}},
            ).modified_count
            stats[view_tag] += count

        # Fallback: documents without internal branch → use source_language_code
        for lang_code, view_tag in _SOURCE_LANG_TO_VIEW.items():
            count = docs.update_many(
                {
                    "dialect_view": {"$exists": False},
                    "metadata.source_language_code": lang_code,
                },
                {"$set": {"dialect_view": view_tag}},
            ).modified_count
            stats[view_tag] += count

        # Last resort: anything still untagged → unknown
        remaining = docs.update_many(
            {"dialect_view": {"$exists": False}},
            {"$set": {"dialect_view": "unknown"}},
        ).modified_count
        stats["unknown"] = remaining

        client.metadata.replace_one(
            {"stage": "materialize_dialect_views"},
            {
                "stage": "materialize_dialect_views",
                "timestamp": datetime.now(timezone.utc),
                "total_documents": total,
                "dialect_distribution": stats,
                "wa_pct": round(stats["wa"] / total * 100, 1) if total else 0,
                "ea_pct": round(stats["ea"] / total * 100, 1) if total else 0,
                "eng_pct": round(stats.get("eng", 0) / total * 100, 1) if total else 0,
            },
            upsert=True,
        )

        print("Dialect materialization complete")
        print(f"  total: {total}")
        for tag, count in sorted(stats.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1) if total else 0
            print(f"  {tag}: {count} ({pct}%)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run({})
