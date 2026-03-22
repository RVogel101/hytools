"""Investigate Western Armenian documents in the MongoDB `documents` collection.

Usage:
    python 07-tools/investigate_wa_docs.py --top 20 --sample 5

Outputs:
 - total documents
 - total documents with internal_language_branch == 'hye-w'
 - top sources overall (by doc count)
 - top sources among WA docs
 - per-source WA fraction for top sources
 - sample WA document ids/titles
"""
from __future__ import annotations

import argparse
from collections import Counter
from hytool.ingestion._shared.helpers import open_mongodb_client


def run(limit_sources: int = 20, sample_per_source: int = 3, config: dict | None = None) -> None:
    with open_mongodb_client(config or {}) as client:
        if client is None:
            raise RuntimeError("MongoDB required")
        docs = client.documents

        total_docs = docs.count_documents({})
        wa_query = {"internal_language_branch": "hye-w"}
        wa_docs = docs.count_documents(wa_query)

        print(f"Total documents in corpus: {total_docs}")
        print(f"Western Armenian documents (internal_language_branch=='hye-w'): {wa_docs}")
        if total_docs:
            print(f"WA fraction: {wa_docs/total_docs:.4f}")

        # Top sources overall
        pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit_sources},
        ]
        top_sources = list(docs.aggregate(pipeline))
        print("\nTop sources overall:")
        for s in top_sources:
            print(f"  {s.get('_id')}: {s.get('count')}")

        # Top sources for WA docs
        pipeline_wa = [
            {"$match": wa_query},
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit_sources},
        ]
        top_wa_sources = list(docs.aggregate(pipeline_wa))
        print("\nTop sources for Western Armenian docs:")
        for s in top_wa_sources:
            print(f"  {s.get('_id')}: {s.get('count')}")

        # Per-source WA fraction for the union of top sources
        interesting = [s.get('_id') for s in top_sources]
        interesting_wa = [s.get('_id') for s in top_wa_sources]
        union = list(dict.fromkeys(interesting_wa + interesting))[:limit_sources]
        print("\nWA fraction by top sources:")
        for src in union:
            total = docs.count_documents({"source": src})
            wa = docs.count_documents({"source": src, "internal_language_branch": "hye-w"})
            frac = wa / total if total else 0.0
            print(f"  {src}: WA {wa} / {total} = {frac:.3f}")

        # Sample WA docs (show id, title, source)
        print(f"\nSample Western Armenian documents (up to {sample_per_source}):")
        cursor = docs.find(wa_query, {"_id": 1, "title": 1, "source": 1}).limit(sample_per_source)
        for d in cursor:
            print(f"  id={d.get('_id')}, source={d.get('source')}, title={d.get('title')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investigate Western Armenian docs in MongoDB")
    parser.add_argument("--top", type=int, default=20, help="Top N sources to show")
    parser.add_argument("--sample", type=int, default=5, help="Sample WA docs to print")
    parser.add_argument("--config", type=str, default=None, help="Optional YAML config path")
    args = parser.parse_args()

    cfg = None
    if args.config:
        import yaml
        with open(args.config, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

    run(limit_sources=args.top, sample_per_source=args.sample, config=cfg)

