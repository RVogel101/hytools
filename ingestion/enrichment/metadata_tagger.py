"""Dialect-aware metadata enrichment for MongoDB corpus documents.

Provides source-to-metadata mapping so each document in MongoDB gets
structured metadata (dialect, region, source_type, confidence scores, etc.)
applied at query time or as a batch enrichment pass.

How metadata_tagger knows source, url, author:
  These are stored at insert time by scrapers and ``insert_document``.
  The document has top-level ``source`` and ``metadata.url``, ``metadata.author``.
  metadata_tagger reads the document and uses ``source`` to look up enrichment;
  it only adds/backfills dialect, region, source_name, confidence, and placeholders.
  It does not overwrite url or author.

Two usage patterns:

1. **Inline at insert time** — scrapers call ``get_source_metadata(source)``
   to obtain a dict that gets merged into the ``metadata`` kwarg of
   ``insert_or_skip`` / ``client.insert_document``.

2. **Batch post-processing** — ``run(config)`` iterates all MongoDB documents
   and backfills any that lack structured metadata fields.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from ingestion._shared.metadata import (
    TextMetadata,
    Dialect,
    DialectSubcategory,
    Region,
    SourceType,
    ContentType,
    WritingCategory,
)

logger = logging.getLogger(__name__)


SOURCE_METADATA: dict[str, dict] = {
    "wikipedia": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "language_code": "hyw",
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Wikipedia (hyw)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_dialect": 0.99,
        "confidence_region": 1.0,
    },
    "wikipedia_ea": {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "language_code": "hye",
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Wikipedia (hye)",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_dialect": 0.95,
        "confidence_region": 0.85,
    },
    "wikisource": {
        "source_type": SourceType.LITERATURE,
        "source_name": "Wikisource (hye)",
        "content_type": ContentType.LITERATURE,
        "writing_category": WritingCategory.LITERATURE,
        "confidence_dialect": 0.90,
        "confidence_region": 0.70,
    },
    "archive_org": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.ARCHIVE,
        "source_name": "Internet Archive",
        "region": Region.WESTERN_OTHER,
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_dialect": 0.80,
        "confidence_region": 0.70,
    },
    "hathitrust": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "source_type": SourceType.LIBRARY,
        "source_name": "HathiTrust Digital Library",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_dialect": 0.75,
        "confidence_region": 0.60,
    },
    "gallica": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "source_type": SourceType.LIBRARY,
        "source_name": "Gallica (BnF)",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_dialect": 0.75,
        "confidence_region": 0.60,
    },
    "loc": {
        "source_type": SourceType.LIBRARY,
        "source_name": "Library of Congress",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_dialect": 0.70,
        "confidence_region": 0.60,
    },
    "dpla": {
        "source_type": SourceType.LIBRARY,
        "source_name": "DPLA (Digital Public Library of America)",
        "content_type": ContentType.LITERATURE,
        "writing_category": WritingCategory.BOOK,
        "confidence_dialect": 0.5,
        "confidence_region": 0.50,
    },
    "newspaper:aztagdaily": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Aztag Daily",
        "region": Region.LEBANON,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.95,
        "confidence_region": 0.95,
    },
    "newspaper:horizonweekly": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Horizon Weekly",
        "region": Region.CANADA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.95,
        "confidence_region": 0.95,
    },
    "newspaper:asbarez": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Asbarez",
        "region": Region.CALIFORNIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.85,
        "confidence_region": 0.90,
    },
    # Aliases for newspaper scraper source keys (aztag/horizon match aztagdaily/horizonweekly)
    "newspaper:aztag": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Aztag Daily",
        "region": Region.LEBANON,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.95,
        "confidence_region": 0.95,
    },
    "newspaper:horizon": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Horizon Weekly",
        "region": Region.CANADA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.95,
        "confidence_region": 0.95,
    },
    "eastern_armenian_news:armenpress": {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Armenpress",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.98,
        "confidence_region": 0.99,
    },
    "eastern_armenian_news:a1plus": {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "A1+",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.98,
        "confidence_region": 0.99,
    },
    "eastern_armenian_news:armtimes": {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Armtimes",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.98,
        "confidence_region": 0.99,
    },
    "eastern_armenian_news:aravot": {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Aravot",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.98,
        "confidence_region": 0.99,
    },
    "culturax": {
        "source_type": SourceType.WEBSITE,
        "source_name": "CulturaX (HuggingFace)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_dialect": 0.80,
        "confidence_region": 0.50,
    },
    "english_sources:wikipedia_history": {
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "English Wikipedia (Armenian history)",
        "language_code": "en",
        "content_type": ContentType.ACADEMIC,
        "writing_category": WritingCategory.HISTORY,
        "confidence_dialect": 0.0,
        "confidence_region": 0.0,
    },
    "english_sources:hyestart": {
        "source_type": SourceType.WEBSITE,
        "source_name": "Hyestart.am",
        "language_code": "en",
        "content_type": ContentType.ACADEMIC,
        "writing_category": WritingCategory.ACADEMIC,
        "confidence_dialect": 0.0,
        "confidence_region": 0.0,
    },
    "english_sources:csufresno": {
        "source_type": SourceType.ACADEMIC,
        "source_name": "CSU Fresno Armenian Studies",
        "language_code": "en",
        "content_type": ContentType.ACADEMIC,
        "writing_category": WritingCategory.ACADEMIC,
        "confidence_dialect": 0.0,
        "confidence_region": 0.0,
    },
    "nayiri": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Nayiri Dictionary",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_dialect": 0.90,
        "confidence_region": 0.70,
    },
    "mss_nkr": {
        "source_type": SourceType.ARCHIVE,
        "source_name": "Matenadaran NKR",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.MANUSCRIPT,
        "confidence_dialect": 0.60,
        "confidence_region": 0.50,
    },
    "anki_lexicon": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Anki Flashcards (Lexicon)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_dialect": 0.95,
        "confidence_region": 0.50,
    },
    "anki_sentences": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Anki Flashcards (Sentences)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_dialect": 0.95,
        "confidence_region": 0.50,
    },
    "gomidas": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.ARCHIVE,
        "source_name": "Gomidas Institute",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.85,
        "confidence_region": 0.70,
    },
    "ocr_ingest": {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.ARCHIVE,
        "source_name": "OCR ingest",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_dialect": 0.75,
        "confidence_region": 0.50,
    },
}

_GENERIC_PREFIXES = [
    "newspaper:",
    "eastern_armenian_news:",
    "english_sources:",
    "rss_news:",
]


class CorpusMetadataTagger:
    """Thin wrapper exposing CORPUS_CONFIGS for tests and external consumers.

    CORPUS_CONFIGS maps source identifiers (including legacy keys like
    wikipedia/extracted, newspapers/aztag) to metadata dicts.
    """

    CORPUS_CONFIGS: dict[str, dict] = dict(SOURCE_METADATA)
    CORPUS_CONFIGS["wikipedia/extracted"] = SOURCE_METADATA["wikipedia"]
    CORPUS_CONFIGS["newspapers/aztag"] = SOURCE_METADATA["newspaper:aztagdaily"]
    CORPUS_CONFIGS["newspapers/horizon"] = SOURCE_METADATA["newspaper:horizonweekly"]
    CORPUS_CONFIGS["news_ea/aravot"] = SOURCE_METADATA["eastern_armenian_news:aravot"]
    CORPUS_CONFIGS["news_ea/russian_influence"] = {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_RUSSIAN_INFLUENCE,
        "language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Eastern Armenian (Russian influence)",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.90,
        "confidence_region": 0.80,
    }
    CORPUS_CONFIGS["news_ea/iran"] = {
        "dialect": Dialect.EASTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.EASTERN_IRAN,
        "language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Eastern Armenian (Iran)",
        "region": Region.IRAN,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_dialect": 0.90,
        "confidence_region": 0.85,
    }
    CORPUS_CONFIGS["armeno_turkish"] = {
        "dialect": Dialect.WESTERN_ARMENIAN,
        "dialect_subcategory": DialectSubcategory.ARMENO_TURKISH,
        "source_type": SourceType.LITERATURE,
        "source_name": "Armeno-Turkish",
        "content_type": ContentType.LITERATURE,
        "writing_category": WritingCategory.LITERATURE,
        "confidence_dialect": 0.95,
        "confidence_region": 0.70,
    }


def get_source_metadata(source: str) -> dict:
    """Return enrichment metadata dict for a given source identifier.

    Tries exact match first, then prefix-based fallback for compound sources
    like ``newspaper:aztagdaily`` or ``eastern_armenian_news:armenpress``.

    Returns a flat dict suitable for merging into the ``metadata`` kwarg
    of ``insert_or_skip`` / ``MongoDBCorpusClient.insert_document``.

    Note: source, url, author are stored at insert time by scrapers and
    insert_document; metadata_tagger only enriches with dialect, region,
    source_name, confidence scores, and placeholder author fields.
    """
    cfg = SOURCE_METADATA.get(source)

    if cfg is None:
        for prefix in _GENERIC_PREFIXES:
            if source.startswith(prefix):
                base = prefix.rstrip(":")
                cfg = SOURCE_METADATA.get(base)
                break

    if cfg is None:
        return {}

    meta: dict = {}
    for key in ("source_name", "language_code", "confidence_dialect", "confidence_region"):
        if key in cfg:
            meta[key] = cfg[key]

    for key in ("dialect", "dialect_subcategory", "region", "source_type", "content_type", "writing_category"):
        val = cfg.get(key)
        if val is not None:
            meta[key] = val.value if hasattr(val, "value") else val

    # Placeholder fields for future author-level enrichment (models, conditional coding).
    # Will be populated later; None for now.
    meta["author_region_approximate"] = None
    meta["author_dialect_specific_approximate"] = None

    return meta


def _enrich_document(doc: dict, source: str) -> dict | None:
    """Build a ``$set`` update dict for a single document.

    Returns None if the document already has structured metadata or there
    is no config for the source.
    """
    existing = doc.get("metadata", {})
    if existing.get("source_type") and existing.get("confidence_dialect") is not None:
        return None

    enrichment = get_source_metadata(source)
    if not enrichment:
        return None

    updates: dict = {}
    for key, value in enrichment.items():
        if existing.get(key) is None:
            updates[f"metadata.{key}"] = value

    if not updates:
        return None

    updates["metadata.enrichment_date"] = datetime.now(timezone.utc).isoformat()
    return updates


def run(config: dict) -> None:
    """Batch-enrich all MongoDB documents with structured metadata.

    Iterates every document, looks up its ``source`` field in
    ``SOURCE_METADATA``, and backfills any missing metadata fields.
    Also backfills ``metadata.char_count`` and ``metadata.word_count``
    when missing (from document text). Already-enriched documents are
    skipped for dialect/source metadata but may still receive stats.

    Optional: set config ``scraping.metadata_tagger.output_csv`` to a path
    (or True for default data/logs/metadata_tagger_report.csv) to write a
    machine-readable CSV with document_id, source, char_count, word_count, enriched.
    """
    from pathlib import Path

    from ingestion._shared.helpers import open_mongodb_client

    scrape_cfg = config.get("scraping", {}).get("metadata_tagger", {}) or {}
    output_csv = scrape_cfg.get("output_csv")
    csv_path: Path | None = None
    if output_csv is True:
        csv_path = Path(config.get("paths", {}).get("log_dir", "data/logs")) / "metadata_tagger_report.csv"
    elif output_csv and isinstance(output_csv, (str, Path)):
        csv_path = Path(output_csv)
    csv_rows: list[dict] = []

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for metadata enrichment")

        docs = client.documents
        total = docs.count_documents({})
        enriched = 0
        skipped = 0
        stats_updated = 0

        cursor = docs.find(
            {},
            {"source": 1, "metadata": 1, "text": 1},
        )

        for doc in cursor:
            source = doc.get("source", "")
            text = doc.get("text") or ""
            char_count = len(text)
            word_count = len(text.split())
            existing = doc.get("metadata", {})

            updates = _enrich_document(doc, source)
            needs_stats = existing.get("char_count") is None or existing.get("word_count") is None
            stats_update = {}
            if needs_stats:
                stats_update["metadata.char_count"] = char_count
                stats_update["metadata.word_count"] = word_count

            if updates is not None:
                updates.update(stats_update)
                updates["metadata.enrichment_date"] = datetime.now(timezone.utc).isoformat()
                docs.update_one({"_id": doc["_id"]}, {"$set": updates})
                enriched += 1
                if csv_path:
                    csv_rows.append({
                        "document_id": str(doc["_id"]),
                        "source": source,
                        "char_count": char_count,
                        "word_count": word_count,
                        "enriched": "1",
                    })
            else:
                if stats_update:
                    docs.update_one({"_id": doc["_id"]}, {"$set": stats_update})
                    stats_updated += 1
                skipped += 1
                if csv_path:
                    csv_rows.append({
                        "document_id": str(doc["_id"]),
                        "source": source,
                        "char_count": char_count,
                        "word_count": word_count,
                        "enriched": "0",
                    })

        if csv_path and csv_rows:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            import csv as csv_module
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv_module.DictWriter(f, fieldnames=["document_id", "source", "char_count", "word_count", "enriched"])
                w.writeheader()
                w.writerows(csv_rows)
            logger.info("Wrote metadata_tagger report: %s (%d rows)", csv_path, len(csv_rows))

        client.metadata.replace_one(
            {"stage": "metadata_tagger"},
            {
                "stage": "metadata_tagger",
                "timestamp": datetime.now(timezone.utc),
                "total_documents": total,
                "enriched": enriched,
                "skipped_already_tagged": skipped,
                "stats_updated": stats_updated,
            },
            upsert=True,
        )

        logger.info(
            "Metadata enrichment complete: %d enriched, %d skipped (already tagged), %d stats backfilled, %d total",
            enriched, skipped, stats_updated, total,
        )
        print(f"Metadata enrichment: {enriched} enriched, {skipped} already tagged, {stats_updated} stats backfilled, {total} total")
