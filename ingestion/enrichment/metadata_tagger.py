"""Metadata enrichment for MongoDB corpus documents.

Provides source-to-metadata mapping so each document in MongoDB gets
structured metadata (region, source_type, confidence scores, etc.)
applied at query time or as a batch enrichment pass.

How metadata_tagger knows source, url, author:
  These are stored at insert time by scrapers and ``insert_document``.
  The document has top-level ``source`` and ``metadata.url``, ``metadata.author``.
  metadata_tagger reads the document and uses ``source`` to look up enrichment;
  it only adds/backfills region, source_name, confidence, and placeholders.
  It does not overwrite url or author.

Two usage patterns:

1. **Inline at insert time** â€” scrapers call ``get_source_metadata(source)``
   to obtain a dict that gets merged into the ``metadata`` kwarg of
   ``insert_or_skip`` / ``client.insert_document``.

2. **Batch post-processing** â€” ``run(config)`` iterates all MongoDB documents
   and backfills any that lack structured metadata fields.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from ingestion._shared.metadata import (
    TextMetadata,
    DialectSubcategory,
    Region,
    SourceType,
    ContentType,
    WritingCategory,
)

logger = logging.getLogger(__name__)


SOURCE_METADATA: dict[str, dict] = {
    "wikipedia_wa": {
        "source_language_code": "hyw",
        "dialect_subcategory": DialectSubcategory.WESTERN_DIASPORA_GENERAL,
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Wikipedia",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_region": 1.0,
    },
    "wikipedia_ea": {
        "source_language_code": "hye",
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Wikipedia",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_region": 0.85,
    },
    "wikisource": {
        "source_type": SourceType.LITERATURE,
        "source_name": "Wikisource",
        "source_language_code": "hye",
        "content_type": ContentType.LITERATURE,
        "writing_category": WritingCategory.LITERATURE,
        "confidence_region": 0.70,
    },
    "archive_org": {
        "source_type": SourceType.ARCHIVE,
        "source_name": "Internet Archive",
        "region": Region.WESTERN_OTHER,
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_region": 0.70,
    },
    "hathitrust": {
        "source_type": SourceType.LIBRARY,
        "source_name": "HathiTrust Digital Library",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_region": 0.60,
    },
    "gallica": {
        "source_type": SourceType.LIBRARY,
        "source_name": "Gallica (BnF)",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_region": 0.60,
    },
    "loc": {
        "source_type": SourceType.LIBRARY,
        "source_name": "Library of Congress",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
        "confidence_region": 0.60,
    },
    "dpla": {
        "source_type": SourceType.LIBRARY,
        "source_name_shrt": "DPLA",
        "source_name_long": "Digital Public Library of America",
        "content_type": ContentType.LITERATURE,
        "writing_category": WritingCategory.BOOK,
        "confidence_region": 0.50,
    },
    "newspaper:aztagdaily": {
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Aztag Daily",
        "region": Region.LEBANON,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.95,
    },
    "newspaper:horizonweekly": {
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Horizon Weekly",
        "region": Region.CANADA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.95,
    },
    "newspaper:asbarez": {
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Asbarez",
        "region": Region.CALIFORNIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.90,
    },
    # Aliases for newspaper scraper source keys (aztag/horizon match aztagdaily/horizonweekly)
    "newspaper:aztag": {
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Aztag Daily",
        "region": Region.LEBANON,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.95,
    },
    "newspaper:horizon": {
        "source_type": SourceType.NEWSPAPER,
        "source_name": "Horizon Weekly",
        "region": Region.CANADA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.95,
    },
    "newspaper:armenpress": {
        "source_language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Armenpress",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.99,
    },
    "newspaper:a1plus": {
        "source_language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "A1+",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.99,
    },
    "newspaper:armtimes": {
        "source_language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Armtimes",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.99,
    },
    "newspaper:aravot": {
        "source_language_code": "hye",
        "dialect_subcategory": DialectSubcategory.EASTERN_HAYASTAN,
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Aravot",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.99,
    },
    "culturax": {
        "source_type": SourceType.WEBSITE,
        "source_name": "CulturaX (HuggingFace)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_region": 0.50,
    },
    "english_sources:wikipedia_history": {
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "English Wikipedia (Armenian history)",
        "source_language_code": "en",
        "content_type": ContentType.ACADEMIC,
        "writing_category": WritingCategory.HISTORY,
        "confidence_region": 0.0,
    },
    "english_sources:hyestart": {
        "source_type": SourceType.WEBSITE,
        "source_name": "Hyestart.am",
        "source_language_code": "en",
        "content_type": ContentType.ACADEMIC,
        "writing_category": WritingCategory.ACADEMIC,
        "confidence_region": 0.0,
    },
    "english_sources:csufresno": {
        "source_type": SourceType.ACADEMIC,
        "source_name": "CSU Fresno Armenian Studies",
        "source_language_code": "en",
        "content_type": ContentType.ACADEMIC,
        "writing_category": WritingCategory.ACADEMIC,
        "confidence_region": 0.0,
    },
    "nayiri": {
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Nayiri Dictionary",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_region": 0.70,
    },
    "mss_nkr": {
        "source_type": SourceType.ARCHIVE,
        "source_name": "Matenadaran NKR",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.MANUSCRIPT,
        "confidence_region": 0.50,
    },
    "anki_lexicon": {
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Anki Flashcards (Lexicon)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_region": 0.50,
    },
    "anki_sentences": {
        "source_type": SourceType.ENCYCLOPEDIA,
        "source_name": "Anki Flashcards (Sentences)",
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.ARTICLE,
        "confidence_region": 0.50,
    },
    "gomidas": {
        "source_type": SourceType.ARCHIVE,
        "source_name": "Gomidas Institute",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.70,
    },
    "ocr_ingest": {
        "source_type": SourceType.ARCHIVE,
        "source_name": "OCR ingest",
        "content_type": ContentType.HISTORICAL,
        "writing_category": WritingCategory.BOOK,
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
    CORPUS_CONFIGS["wikipedia/extracted"] = SOURCE_METADATA["wikipedia_wa"]
    CORPUS_CONFIGS["newspapers/aztag"] = SOURCE_METADATA["newspaper:aztagdaily"]
    CORPUS_CONFIGS["newspapers/horizon"] = SOURCE_METADATA["newspaper:horizonweekly"]
    CORPUS_CONFIGS["news_ea/aravot"] = SOURCE_METADATA["newspaper:aravot"]
    CORPUS_CONFIGS["news_ea/russian_influence"] = {
        "source_language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Eastern Armenian (Russian influence)",
        "region": Region.ARMENIA,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.80,
    }
    CORPUS_CONFIGS["news_ea/iran"] = {
        "source_language_code": "hye",
        "source_type": SourceType.NEWS_AGENCY,
        "source_name": "Eastern Armenian (Iran)",
        "region": Region.IRAN,
        "content_type": ContentType.ARTICLE,
        "writing_category": WritingCategory.NEWS,
        "confidence_region": 0.85,
    }
    CORPUS_CONFIGS["armeno_turkish"] = {
        "source_type": SourceType.LITERATURE,
        "source_name": "Armeno-Turkish",
        "content_type": ContentType.LITERATURE,
        "writing_category": WritingCategory.LITERATURE,
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
    for key in ("source_name", "source_language_code", "confidence_region"):
        if key in cfg:
            meta[key] = cfg[key]

    for key in ("dialect_subcategory", "region", "source_type", "content_type", "writing_category"):
        val = cfg.get(key)
        if val is not None:
            meta[key] = val.value if hasattr(val, "value") else val

    # Placeholder fields for future author-level enrichment (models, conditional coding).
    # Will be populated later; None for now.
    meta["author_region_approximate"] = None
    meta["author_dialect_specific_approximate"] = None

    return meta


def _enrich_document(doc: dict, source: str, text: str = "", analyzer: object | None = None) -> dict | None:
    """Build a ``$set`` update dict for a single document.

    Returns None if the document already has structured metadata or there
    is no config for the source.

    When *text* is provided, derives ``internal_language_code`` and
    ``internal_language_branch`` via text analysis (``classify_language``).
    """
    from ingestion._shared.helpers import classify_language, compute_wa_score_detailed, compute_script_purity_score, _any_armenian_script

    existing = doc.get("metadata", {})
    if existing.get("source_type") and existing.get("enrichment_date"):
        return None

    enrichment = get_source_metadata(source)
    if not enrichment:
        return None

    updates: dict = {}
    for key, value in enrichment.items():
        if existing.get(key) is None:
            updates[f"metadata.{key}"] = value

    # Derive internal language classification from actual text content
    if text.strip() and existing.get("internal_language_branch") is None:
        lang_code, lang_branch = classify_language(text)
        updates["metadata.internal_language_code"] = lang_code
        updates["metadata.internal_language_branch"] = lang_branch

    # Compute WA score breakdown — applied to every document containing any Armenian script
    if text.strip() and existing.get("wa_score") is None and _any_armenian_script(text):
        updates["metadata.wa_score"] = compute_wa_score_detailed(text)

    # Compute script purity (fraction of Armenian chars — detects OCR contamination)
    if text.strip() and existing.get("script_purity_score") is None:
        updates["metadata.script_purity_score"] = compute_script_purity_score(text)

    # Full quantitative linguistic metrics + loanword profile (Armenian docs only).
    # text_metrics_date acts as the sentinel: present = metrics have been computed.
    if text.strip() and existing.get("text_metrics_date") is None and _any_armenian_script(text):
        try:
            from dataclasses import asdict as _asdict
            from linguistics.metrics.text_metrics import QuantitativeLinguisticsAnalyzer
            from linguistics.lexicon.loanword_tracker import analyze_loanwords

            _qla = analyzer if analyzer is not None else QuantitativeLinguisticsAnalyzer()
            _card = _qla.analyze_text(
                text, text_id=str(doc.get("_id", "")), source=source
            )
            updates["metadata.text_metrics"] = {
                "lexical": _asdict(_card.lexical),
                "syntactic": _asdict(_card.syntactic),
                "morphological": _asdict(_card.morphological),
                "orthographic": _asdict(_card.orthographic),
                "semantic": _asdict(_card.semantic),
                "contamination": _asdict(_card.contamination),
                "quality_flags": _asdict(_card.quality_flags),
            }
            updates["metadata.loanwords"] = analyze_loanwords(
                text, text_id=str(doc.get("_id", "")), source=source
            ).to_dict()
            updates["metadata.text_metrics_date"] = datetime.now(timezone.utc).isoformat()
        except Exception as _tm_exc:
            logger.debug("text_metrics computation failed for doc %s: %s", doc.get("_id"), _tm_exc)

    if not updates:
        return None

    updates["metadata.enrichment_date"] = datetime.now(timezone.utc).isoformat()
    return updates


def _process_doc_for_run(doc: dict, analyzer: object | None) -> dict:
    """Compute all MongoDB updates for one document (primary enrichment + backfill).

    Called by worker threads in ``run()``.  Thread-safe: ``analyzer`` is
    read-only after ``__init__``; all imports are cached after first load.

    Returns a dict with:
      doc_id, source, char_count, word_count,
      write_op (UpdateOne | None),
      was_enriched (bool), was_backfilled (bool),
      text_metrics_computed (bool), text_metrics_error (bool).
    """
    from pymongo import UpdateOne as _UpdateOne

    source = doc.get("source", "")
    text = doc.get("text") or ""
    char_count = len(text)
    word_count = len(text.split())
    existing = doc.get("metadata", {})

    result: dict = {
        "doc_id": doc["_id"],
        "source": source,
        "char_count": char_count,
        "word_count": word_count,
        "write_op": None,
        "was_enriched": False,
        "was_backfilled": False,
        "text_metrics_computed": False,
        "text_metrics_error": False,
    }

    # Stats fields are always backfilled regardless of path
    combined: dict = {}
    if existing.get("char_count") is None or existing.get("word_count") is None:
        combined["metadata.char_count"] = char_count
        combined["metadata.word_count"] = word_count

    primary = _enrich_document(doc, source, text=text, analyzer=analyzer)

    if primary is not None:
        combined.update(primary)
        combined["metadata.enrichment_date"] = datetime.now(timezone.utc).isoformat()
        result["was_enriched"] = True
        result["text_metrics_computed"] = "metadata.text_metrics_date" in combined
    else:
        # Backfill path: already enriched — fill any missing computed fields.
        if text.strip():
            from ingestion._shared.helpers import (
                classify_language,
                compute_wa_score_detailed,
                compute_script_purity_score,
                _any_armenian_script,
            )
            _has_arm = _any_armenian_script(text)

            if existing.get("internal_language_branch") is None:
                lang_code, lang_branch = classify_language(text)
                combined["metadata.internal_language_code"] = lang_code
                combined["metadata.internal_language_branch"] = lang_branch

            if existing.get("wa_score") is None and _has_arm:
                combined["metadata.wa_score"] = compute_wa_score_detailed(text)

            if existing.get("script_purity_score") is None:
                combined["metadata.script_purity_score"] = compute_script_purity_score(text)

            if existing.get("text_metrics_date") is None and _has_arm:
                try:
                    from dataclasses import asdict as _asdict
                    from linguistics.metrics.text_metrics import QuantitativeLinguisticsAnalyzer
                    from linguistics.lexicon.loanword_tracker import analyze_loanwords

                    _qla = analyzer if analyzer is not None else QuantitativeLinguisticsAnalyzer()
                    _card = _qla.analyze_text(
                        text, text_id=str(doc.get("_id", "")), source=source
                    )
                    combined["metadata.text_metrics"] = {
                        "lexical": _asdict(_card.lexical),
                        "syntactic": _asdict(_card.syntactic),
                        "morphological": _asdict(_card.morphological),
                        "orthographic": _asdict(_card.orthographic),
                        "semantic": _asdict(_card.semantic),
                        "contamination": _asdict(_card.contamination),
                        "quality_flags": _asdict(_card.quality_flags),
                    }
                    combined["metadata.loanwords"] = analyze_loanwords(
                        text, text_id=str(doc.get("_id", "")), source=source
                    ).to_dict()
                    combined["metadata.text_metrics_date"] = datetime.now(timezone.utc).isoformat()
                    result["text_metrics_computed"] = True
                except Exception as _tm_exc:
                    result["text_metrics_error"] = True
                    logger.warning(
                        "text_metrics backfill failed for doc %s (source=%s): %s",
                        doc.get("_id"), source, _tm_exc,
                    )

        if combined:
            result["was_backfilled"] = True

    if combined:
        result["write_op"] = _UpdateOne({"_id": doc["_id"]}, {"$set": combined})
    return result


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

        import concurrent.futures

        docs = client.documents
        total = docs.count_documents({})
        enriched = 0
        skipped = 0
        stats_updated = 0
        text_metrics_computed = 0
        text_metrics_errors = 0
        _LOG_INTERVAL = 500

        workers = max(1, scrape_cfg.get("workers", 4))
        chunk_size = max(10, scrape_cfg.get("write_batch_size", 200))

        # Pre-initialize the expensive QuantitativeLinguisticsAnalyzer once and share
        # it across all worker threads.  It is read-only after __init__ → thread-safe.
        _analyzer: object | None = None
        try:
            from linguistics.metrics.text_metrics import QuantitativeLinguisticsAnalyzer as _QLA
            _analyzer = _QLA()
        except Exception as _ae:
            logger.warning(
                "metadata_tagger: could not pre-initialize QuantitativeLinguisticsAnalyzer: %s", _ae
            )

        logger.info(
            "metadata_tagger: starting — %d documents, %d workers, chunk_size=%d",
            total, workers, chunk_size,
        )

        def _worker(doc: dict) -> dict:
            return _process_doc_for_run(doc, _analyzer)

        def _iter_chunks():
            chunk: list = []
            _cursor = docs.find({}, {"source": 1, "metadata": 1, "text": 1})
            for _doc in _cursor:
                chunk.append(_doc)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

        processed = 0
        _last_logged = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for chunk in _iter_chunks():
                results = list(pool.map(_worker, chunk))
                bulk_ops: list = []

                for r in results:
                    processed += 1
                    if r["write_op"] is not None:
                        bulk_ops.append(r["write_op"])
                    if r["was_enriched"]:
                        enriched += 1
                        logger.debug("enriched  source=%-30s chars=%d", r["source"], r["char_count"])
                    else:
                        skipped += 1
                        if r["was_backfilled"]:
                            stats_updated += 1
                            logger.debug("backfilled source=%-30s", r["source"])
                    if r["text_metrics_computed"]:
                        text_metrics_computed += 1
                    if r["text_metrics_error"]:
                        text_metrics_errors += 1
                    if csv_path:
                        csv_rows.append({
                            "document_id": str(r["doc_id"]),
                            "source": r["source"],
                            "char_count": r["char_count"],
                            "word_count": r["word_count"],
                            "enriched": "1" if r["was_enriched"] else "0",
                        })

                if bulk_ops:
                    docs.bulk_write(bulk_ops, ordered=False)

                if processed - _last_logged >= _LOG_INTERVAL:
                    logger.info(
                        "  progress: %d/%d docs — enriched=%d  backfilled=%d  text_metrics=%d  errors=%d",
                        processed, total, enriched, stats_updated, text_metrics_computed, text_metrics_errors,
                    )
                    _last_logged = processed

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
                "text_metrics_computed": text_metrics_computed,
                "text_metrics_errors": text_metrics_errors,
            },
            upsert=True,
        )

        logger.info(
            "Metadata enrichment complete: %d enriched, %d skipped (already tagged), "
            "%d stats backfilled, %d text_metrics computed, %d text_metrics errors, %d total",
            enriched, skipped, stats_updated, text_metrics_computed, text_metrics_errors, total,
        )
        print(f"Metadata enrichment: {enriched} enriched, {skipped} already tagged, {stats_updated} stats backfilled, {total} total")
