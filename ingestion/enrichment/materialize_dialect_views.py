#!/usr/bin/env python3
"""Materialize dialect-specific views from MongoDB corpus.

Tags each document with a canonical ``dialect_view`` field based on the
``language_code`` metadata, enabling fast filtered queries for WA-only training
datasets, EA reference data, etc.

Also stores dialect distribution stats in the ``metadata`` collection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# language_code → dialect_view tag
_LANG_TO_VIEW = {
    "hyw": "wa",
    "hye": "ea",
    "hy": "ea",     # legacy undetermined Armenian → treat as EA for safety
    "hyc": "ea",    # Classical Armenian
}


def run(config: dict) -> None:
    from ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for dialect materialization")

        docs = client.documents
        docs.create_index("dialect_view")

        total = docs.count_documents({})
        stats: dict[str, int] = {"wa": 0, "ea": 0, "mixed": 0, "unknown": 0}

        # Primary: classify by language_code
        for lang_code, view_tag in _LANG_TO_VIEW.items():
            count = docs.update_many(
                {"metadata.language_code": lang_code},
                {"$set": {"dialect_view": view_tag}},
            ).modified_count
            stats[view_tag] += count

        # Fallback: anything still untagged → unknown
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
