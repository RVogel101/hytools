#!/usr/bin/env python3
"""Materialize language branch views from MongoDB corpus.

Policy: Corpus dialect is derived strictly from text model results
(`internal_language_branch`), no source-language fallback for the final
corpus-side `dialect_view` label.

We still preserve source-language metadata as-is (`metadata.source_language_code`) for
audit and provenance, but we do not auto-assign `dialect_view` from it.

Also stores distribution stats in the ``metadata`` collection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# internal_language_branch → dialect_view tag  (primary — text-derived)
from hytools.ingestion._shared.metadata import InternalLanguageBranch

_BRANCH_TO_VIEW = {
    InternalLanguageBranch.WESTERN_ARMENIAN.value: "wa",
    InternalLanguageBranch.EASTERN_ARMENIAN.value: "ea",
    InternalLanguageBranch.ENGLISH.value: "eng",
}



def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

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

        # No fallback to source_language_code.  We keep this strict to avoid coercing
        # data from external source metadata when text classification is unavailable.

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
