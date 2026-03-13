"""Word frequency facets: aggregation and query API.

Uses per-document word_counts stored in metadata.document_metrics at ingest
(database.compute_metrics_on_ingest or scraping.compute_metrics_on_ingest).

Schema (word_frequencies_facets collection):
  - facet: "author" | "source" | "dialect" | "year" | "region"
  - facet_value: str (e.g. author name, source id, "western_armenian", "2020", "Beirut")
  - word: str (Armenian word)
  - count: int (sum of occurrences in documents matching this facet_value)

Indexes: (facet, facet_value, word) unique; (facet, word); (word, facet, facet_value).

Usage::
  python -m ingestion.aggregation.word_frequency_facets aggregate [--config config/settings.yaml]
  python -m ingestion.aggregation.word_frequency_facets query "слово" [--facet author] [--facet-value "Author Name"]
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

FACET_TYPES = ("author", "source", "dialect", "year", "region")


def _get_facet_value(doc: dict, facet: str) -> str | None:
    """Extract facet value from document. Returns None if not present."""
    if facet == "source":
        v = doc.get("source")
        return (v or "unknown").strip() if isinstance(v, str) else "unknown"

    meta = doc.get("metadata") or {}
    if facet == "author":
        v = meta.get("author")
        if not v or not str(v).strip():
            return None
        return str(v).strip()[:500]

    if facet == "dialect":
        v = meta.get("dialect")
        if not v or not str(v).strip():
            return None
        return str(v).strip().lower()

    if facet == "year":
        for key in ("gallica_date", "date_scraped", "date", "publication_year"):
            v = meta.get(key)
            if v is None:
                continue
            if isinstance(v, datetime):
                return str(v.year)
            s = str(v).strip()
            if not s:
                continue
            match = re.search(r"\b(19|20)\d{2}\b", s)
            if match:
                return match.group(0)
            if len(s) >= 4 and s[:4].isdigit():
                return s[:4]
            return s[:50]
        return None

    if facet == "region":
        for key in ("region", "place", "provenance"):
            v = meta.get(key)
            if v and str(v).strip():
                return str(v).strip()[:200]
        return None

    return None


def run(config: dict) -> None:
    """Pipeline stage: build word_frequencies_facets from document_metrics.word_counts.

    Call this from the runner (after frequency_aggregator). Uses the same config
    as other stages (paths, database). No return value; summary is stored in metadata.
    """
    summary = run_aggregation(config)
    logger.info("word_frequency_facets: %d facet entries from %d documents", summary["entries_stored"], summary["total_docs"])


def run_aggregation(config: dict) -> dict:
    """Build word_frequencies_facets from documents that have metadata.document_metrics.word_counts.

    Returns summary dict: total_docs, entries_stored.
    """
    from ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for word frequency facets")

        docs_col = client.documents
        facet_col = client.db["word_frequencies_facets"]

        agg: dict[tuple[str, str, str], int] = {}
        total_docs = 0
        projection = {
            "source": 1,
            "metadata.author": 1,
            "metadata.dialect": 1,
            "metadata.gallica_date": 1,
            "metadata.date_scraped": 1,
            "metadata.date": 1,
            "metadata.publication_year": 1,
            "metadata.region": 1,
            "metadata.place": 1,
            "metadata.provenance": 1,
            "metadata.document_metrics.word_counts": 1,
        }

        cursor = docs_col.find(
            {"metadata.document_metrics.word_counts": {"$exists": True, "$ne": None}},
            projection,
        )

        for doc in cursor:
            total_docs += 1
            word_counts = (doc.get("metadata") or {}).get("document_metrics") or {}
            wc = word_counts.get("word_counts")
            if not isinstance(wc, dict):
                continue

            for facet in FACET_TYPES:
                fv = _get_facet_value(doc, facet)
                if fv is None or fv == "":
                    continue
                for word, count in wc.items():
                    if not word or not isinstance(count, (int, float)):
                        continue
                    key = (facet, fv, word)
                    agg[key] = agg.get(key, 0) + int(count)

            if total_docs % 5000 == 0:
                logger.info("Facet aggregation: %d docs processed...", total_docs)

        logger.info(
            "Facet aggregation: %d docs with word_counts, %d (facet, facet_value, word) keys",
            total_docs, len(agg),
        )

        facet_col.drop()
        if agg:
            entries = [
                {"facet": f, "facet_value": fv, "word": w, "count": c}
                for (f, fv, w), c in agg.items()
            ]
            facet_col.insert_many(entries)
            facet_col.create_index([("facet", 1), ("facet_value", 1), ("word", 1)], unique=True)
            facet_col.create_index([("facet", 1), ("word", 1)])
            facet_col.create_index([("word", 1), ("facet", 1), ("facet_value", 1)])

        summary = {"total_docs": total_docs, "entries_stored": len(agg)}
        client.metadata.replace_one(
            {"stage": "word_frequency_facets"},
            {"stage": "word_frequency_facets", "timestamp": datetime.utcnow(), **summary},
            upsert=True,
        )
        return summary


def query(
    word: str,
    facet: str | None = None,
    facet_value: str | None = None,
    config: dict | None = None,
    client: Any = None,
) -> int | list:
    """Query facet-based word frequency.

    Returns:
        - int when facet and facet_value are both set (single count).
        - list of (facet_value, count) when only facet is set.
        - list of (facet, facet_value, count) when neither is set (all facets for this word).
    """
    if client is None:
        from ingestion._shared.helpers import open_mongodb_client
        with open_mongodb_client(config or {}) as c:
            if c is None:
                raise RuntimeError("MongoDB required for query")
            return query(word, facet=facet, facet_value=facet_value, config=config, client=c)

    facet_col = client.db["word_frequencies_facets"]
    q: dict = {"word": word}
    if facet:
        q["facet"] = facet
    if facet_value is not None:
        q["facet_value"] = facet_value

    if facet and facet_value is not None:
        doc = facet_col.find_one(q, {"count": 1})
        return doc["count"] if doc else 0

    if facet:
        cursor = facet_col.find(q, {"facet_value": 1, "count": 1}).sort("count", -1)
        return [(d["facet_value"], d["count"]) for d in cursor]

    cursor = facet_col.find(q, {"facet": 1, "facet_value": 1, "count": 1}).sort("count", -1)
    return [(d["facet"], d["facet_value"], d["count"]) for d in cursor]


def run_query_cli(
    word: str,
    facet: str | None = None,
    facet_value: str | None = None,
    config: dict | None = None,
) -> None:
    """Print query result to stdout."""
    result = query(word, facet=facet, facet_value=facet_value, config=config)
    if isinstance(result, int):
        print(result)
        return
    if result and isinstance(result[0], tuple):
        if len(result[0]) == 2:
            for fv, count in result:
                print(f"{fv}\t{count}")
        else:
            for f, fv, count in result:
                print(f"{f}\t{fv}\t{count}")
    else:
        print("0")


if __name__ == "__main__":
    import argparse
    import yaml
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Word frequency facets: aggregate and query")
    sub = parser.add_subparsers(dest="command")
    agg_p = sub.add_parser("aggregate", help="Build word_frequencies_facets from document_metrics.word_counts")
    agg_p.add_argument("--config", type=Path, default=Path("config/settings.yaml"))
    q_p = sub.add_parser("query", help="Query frequency for a word (optionally by facet)")
    q_p.add_argument("word", help="Armenian word")
    q_p.add_argument("--facet", choices=FACET_TYPES, default=None)
    q_p.add_argument("--facet-value", dest="facet_value", default=None)
    q_p.add_argument("--config", type=Path, default=Path("config/settings.yaml"))

    args = parser.parse_args()
    cfg = {}
    config_path = getattr(args, "config", None)
    if config_path and getattr(config_path, "exists", lambda: False)():
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    if args.command == "aggregate":
        summary = run_aggregation(cfg)
        print(f"Stored {summary['entries_stored']} facet entries from {summary['total_docs']} documents")
    elif args.command == "query":
        run_query_cli(
            args.word,
            facet=getattr(args, "facet", None),
            facet_value=getattr(args, "facet_value", None),
            config=cfg,
        )
    else:
        parser.print_help()
