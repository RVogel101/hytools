"""Targeted catalog backfill driven by acquisition priority source targets.

This module consumes the itemized acquisition rows already persisted in
MongoDB, uses their `source_targets` hints to query selected catalog sources,
and writes the discovered catalog items back to MongoDB. It also performs a
conservative inventory title cleanup pass before searching so mixed-script OCR
garbage does not keep polluting the backfill queue.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Sequence

from hytools.config.settings import load_config
from hytools.ingestion._shared.helpers import open_mongodb_client, save_catalog_to_mongodb
from hytools.ingestion.discovery.book_inventory import (
    BookInventoryManager,
    assess_title_plausibility,
    normalize_inventory_title,
)

logger = logging.getLogger(__name__)

_BACKFILL_STAGE = "catalog_backfill"
_TITLE_FROM_DESCRIPTION_RE = re.compile(r"Missing work: '([^']+)' by (.+?)(?: \((\d{4})\))?$")
_ARMENIAN_TERM_RE = re.compile(r"[\u0530-\u058F]{3,}")
_SUPPORTED_SOURCES = ("loc", "archive_org", "hathitrust", "nayiri")
_SOURCE_LABELS = {
    "loc": "Library of Congress",
    "archive_org": "Archive.org",
    "hathitrust": "HathiTrust",
    "nayiri": "Nayiri",
}


def _coerce_year(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_row_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    title = normalize_inventory_title(str(metadata.get("title") or ""))
    authors = str(metadata.get("authors") or "").strip()
    year = _coerce_year(metadata.get("year"))
    description = str(row.get("description") or "")

    if not title:
        match = _TITLE_FROM_DESCRIPTION_RE.match(description)
        if match:
            title = normalize_inventory_title(match.group(1))
            if not authors:
                authors = match.group(2).strip()
            if year is None:
                year = _coerce_year(match.group(3))

    query = str(row.get("acquisition_query") or "").strip()
    if not query:
        query = " ".join(part for part in (title, authors, str(year) if year else "") if part).strip()

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "query": query,
    }


def _source_query(source: str, row_meta: dict[str, Any], target: dict[str, Any]) -> str:
    query = str(target.get("query") or row_meta.get("query") or "").strip()
    if source == "nayiri":
        # Nayiri is a local corpus/lexicon source, not a remote bibliographic API.
        return normalize_inventory_title(str(row_meta.get("title") or "")) or query
    return query


def _significant_armenian_terms(*chunks: str) -> list[str]:
    terms: list[str] = []
    for chunk in chunks:
        for token in _ARMENIAN_TERM_RE.findall(chunk or ""):
            cleaned = normalize_inventory_title(token)
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
    return terms


def _search_nayiri_local(client: Any, row_meta: dict[str, Any], max_results: int) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    if client is None:
        return catalog

    title = str(row_meta.get("title") or "")
    authors = str(row_meta.get("authors") or "")
    query = str(row_meta.get("query") or title or "")
    terms = []
    if title:
        terms.append(title)
    for term in _significant_armenian_terms(title, authors, query):
        if term not in terms:
            terms.append(term)

    entries = client.db.get_collection("nayiri_entries")
    for term in terms[:5]:
        cursor = entries.find(
            {"headword": {"$regex": re.escape(term), "$options": "i"}},
            {"headword": 1},
        ).limit(max_results)
        for doc in cursor:
            headword = str(doc.get("headword") or "").strip()
            if not headword:
                continue
            item_id = f"headword:{headword}"
            if item_id in catalog:
                continue
            catalog[item_id] = {
                "title": headword,
                "query_source": query,
                "match_type": "lexicon_headword",
                "downloaded": False,
            }
            if len(catalog) >= max_results:
                return catalog

    if title:
        cursor = client.documents.find(
            {
                "source": "nayiri_wa_corpus",
                "text": {"$regex": re.escape(title)},
            },
            {"title": 1},
        ).limit(max_results)
        for doc in cursor:
            doc_title = str(doc.get("title") or "").strip() or title
            item_id = f"corpus:{doc_title}"
            if item_id in catalog:
                continue
            catalog[item_id] = {
                "title": doc_title,
                "query_source": query,
                "match_type": "corpus_text_match",
                "downloaded": False,
            }
            if len(catalog) >= max_results:
                break

    return catalog


def _search_source(client: Any, source: str, query: str, row_meta: dict[str, Any], max_per_query: int) -> dict[str, dict[str, Any]]:
    if not query:
        return {}

    if source == "loc":
        from hytools.ingestion.acquisition.loc import search_items as search_loc_items

        return search_loc_items([query], max_per_query=max_per_query)

    if source == "archive_org":
        from hytools.ingestion.acquisition.archive_org import search_items as search_archive_items

        return search_archive_items([query], max_per_query=max_per_query)

    if source == "hathitrust":
        from hytools.ingestion.acquisition.hathitrust import search_items as search_hathi_items

        return search_hathi_items([query], max_per_query=max_per_query, include_seed_list=False)

    if source == "nayiri":
        return _search_nayiri_local(client, row_meta, max_results=max_per_query)

    return {}


def _annotate_catalog_items(
    catalog: dict[str, dict[str, Any]],
    *,
    row: dict[str, Any],
    row_meta: dict[str, Any],
    query: str,
    run_id: str,
) -> dict[str, dict[str, Any]]:
    annotated: dict[str, dict[str, Any]] = {}
    for item_id, item in catalog.items():
        annotated[item_id] = {
            **item,
            "query_source": item.get("query_source") or query,
            "backfill_run_id": run_id,
            "inventory_title": row_meta.get("title"),
            "inventory_authors": row_meta.get("authors"),
            "inventory_year": row_meta.get("year"),
            "priority": row.get("priority"),
            "gap_description": row.get("description"),
        }
    return annotated


def _merge_catalog_hits_into_inventory(
    manager: BookInventoryManager,
    *,
    source: str,
    row_meta: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
) -> int:
    title = normalize_inventory_title(str(row_meta.get("title") or ""))
    if not title or not catalog:
        return 0

    matches = manager.find_by_title(title) or manager.find_by_title(title, fuzzy=True)
    if not matches:
        return 0

    source_label = _SOURCE_LABELS.get(source, source)
    first_item_id = next(iter(catalog), None)
    updated = 0
    for book in matches:
        changed = False

        if source_label not in book.source_discovered_from:
            book.source_discovered_from.append(source_label)
            changed = True

        if source == "loc" and first_item_id and not book.loc_control_number:
            book.loc_control_number = first_item_id
            changed = True
        elif source == "archive_org" and first_item_id and not book.archive_org_id:
            book.archive_org_id = first_item_id
            changed = True
        elif source == "hathitrust" and first_item_id:
            tag = f"hathitrust:{first_item_id}"
            if tag not in book.tags:
                book.tags.append(tag)
                changed = True
        elif source == "nayiri" and first_item_id:
            tag = f"nayiri_match:{first_item_id}"
            if tag not in book.tags:
                book.tags.append(tag)
                changed = True

        if changed:
            book.metadata_last_updated = datetime.now().isoformat()
            updated += 1

    return updated


def run_targeted_backfill(
    config: dict[str, Any],
    *,
    priority: str = "high",
    limit: int = 10,
    max_per_query: int = 5,
    sources: Sequence[str] = _SUPPORTED_SOURCES,
    cleanup_inventory: bool = True,
) -> dict[str, Any]:
    run_id = f"{_BACKFILL_STAGE}:{priority}:{limit}:{max_per_query}"
    source_set = {source for source in sources if source in _SUPPORTED_SOURCES}
    if not source_set:
        raise ValueError("No supported backfill sources were requested")

    manager = BookInventoryManager(config=config)
    cleanup_stats = {
        "total_books": len(manager.books),
        "normalized_titles": 0,
        "flagged_implausible_titles": 0,
        "cleared_implausible_flags": 0,
    }
    if cleanup_inventory:
        cleanup_stats = manager.cleanup_titles()

    summary: dict[str, Any] = {
        "priority": priority,
        "limit": limit,
        "max_per_query": max_per_query,
        "sources": sorted(source_set),
        "cleanup": cleanup_stats,
        "rows_loaded": 0,
        "rows_processed": 0,
        "rows_skipped_implausible": 0,
        "catalog_items_upserted": Counter(),
        "inventory_updates": Counter(),
        "queries_with_hits": Counter(),
    }

    inventory_dirty = any(cleanup_stats[key] for key in ("normalized_titles", "flagged_implausible_titles", "cleared_implausible_flags"))

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB unavailable; targeted catalog backfill requires a working database connection")

        if limit <= 0:
            rows = []
        else:
            rows = list(
                client.acquisition_priority_items.find(
                    {
                        "priority_filter": "all",
                        "priority": priority,
                        "type": "work",
                    },
                    {
                        "_id": 0,
                        "priority": 1,
                        "type": 1,
                        "description": 1,
                        "acquisition_query": 1,
                        "source_targets": 1,
                        "metadata": 1,
                        "impact_score": 1,
                    },
                )
                .sort([("impact_score", -1)])
                .limit(int(limit))
            )
        summary["rows_loaded"] = len(rows)

        for row in rows:
            row_meta = _extract_row_metadata(row)
            plausible_title, _reasons = assess_title_plausibility(row_meta.get("title", ""))
            if not plausible_title:
                summary["rows_skipped_implausible"] += 1
                continue

            selected_targets = [
                target
                for target in (row.get("source_targets") or [])
                if str(target.get("source") or "") in source_set
            ]
            if not selected_targets:
                continue

            summary["rows_processed"] += 1
            for target in selected_targets:
                source = str(target.get("source") or "")
                query = _source_query(source, row_meta, target)
                if not query:
                    continue
                logger.info("Catalog backfill: %s -> %s", source, query)

                catalog = _search_source(client, source, query, row_meta, max_per_query=max_per_query)
                if not catalog:
                    continue

                summary["queries_with_hits"][source] += 1
                annotated_catalog = _annotate_catalog_items(
                    catalog,
                    row=row,
                    row_meta=row_meta,
                    query=query,
                    run_id=run_id,
                )
                summary["catalog_items_upserted"][source] += save_catalog_to_mongodb(client, source, annotated_catalog)
                updates = _merge_catalog_hits_into_inventory(
                    manager,
                    source=source,
                    row_meta=row_meta,
                    catalog=annotated_catalog,
                )
                if updates:
                    summary["inventory_updates"][source] += updates
                    inventory_dirty = True

        if inventory_dirty:
            manager.save_inventory()

        rendered_summary = {
            **summary,
            "catalog_items_upserted": dict(summary["catalog_items_upserted"]),
            "inventory_updates": dict(summary["inventory_updates"]),
            "queries_with_hits": dict(summary["queries_with_hits"]),
            "inventory_saved": inventory_dirty,
        }
        client.log_pipeline_run(_BACKFILL_STAGE, "ok", rendered_summary)
        return rendered_summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run targeted catalog backfill from acquisition priority source targets")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--priority", default="high")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-per-query", type=int, default=5)
    parser.add_argument(
        "--sources",
        nargs="+",
        default=list(_SUPPORTED_SOURCES),
        help="Subset of sources to query (loc archive_org hathitrust nayiri)",
    )
    parser.add_argument("--no-cleanup", action="store_true", help="Skip the inventory title cleanup pass")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    config = load_config(args.config)
    summary = run_targeted_backfill(
        config,
        priority=args.priority,
        limit=args.limit,
        max_per_query=args.max_per_query,
        sources=args.sources,
        cleanup_inventory=not args.no_cleanup,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    raise SystemExit(main())