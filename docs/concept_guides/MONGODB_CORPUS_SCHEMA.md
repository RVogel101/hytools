# MongoDB Corpus Schema

Full documentation of the MongoDB schema used by armenian-corpus-core. All scrapers, the metadata tagger, frequency aggregator, augmentation pipeline, and research tools conform to this structure.

**Database name:** Configurable via `database.mongodb_database` (default: `western_armenian_corpus`).

---

## Collections overview

| Collection | Purpose |
|------------|---------|
| `documents` | Corpus documents (text, hashes, metadata, processing flags) |
| `catalogs` | Source catalogs (LOC, HathiTrust, archive_org, Gallica, etc.) |
| `news_article_catalog` | RSS-derived article metadata (one doc per URL); links to `documents` via `document_id`; tagged with language_code, content_type, writing_category. See [NEWS_AND_RSS_CATALOG.md](NEWS_AND_RSS_CATALOG.md). |
| `metadata` | Pipeline stage metadata (frequency_aggregator, metadata_tagger runs) |
| `word_frequencies` | Unified word frequency list (weighted by source) |
| `word_frequencies_facets` | Per-facet word counts (author, source, dialect, year, region) |
| `book_inventory` | Book inventory entries (WorldCat, LOC, coverage status) |
| `author_profiles` | Author profiles for research pipeline |
| `augmentation_checkpoint` | Completed augmentation task UIDs (resume support) |
| `augmentation_metrics` | Augmentation metric reports and per-task metric cards |
| `dialect_clustering` | PCA/DBSCAN artifacts and sweep results (optional) |
| `etymology` | Lemma → source, confidence, etymology text, relationships (Phase 1: Wiktextract) |
| **GridFS:** `source_binaries` | PDF/image binaries for OCR (chunked storage) |

---

## 1. `documents`

Corpus documents inserted by scrapers and `insert_or_skip` / `MongoDBCorpusClient.insert_document`.

### Schema

```python
{
    "_id": ObjectId,
    "source": str,                      # e.g. "newspaper:aztag", "eastern_armenian_news:armenpress", "loc", "augmented"
    "title": str,
    "text": str,
    "content_hash": str,                # SHA256 of raw text (deduplication; unique index)
    "normalized_content_hash": str,    # SHA256 of NFKC-normalized, whitespace-collapsed text
    "metadata": {
        # Provenance (set at insert)
        "url": str | None,
        "author": str | None,
        "date_scraped": datetime,
        "publication_date": str | None,
        "word_count": int,
        "char_count": int,

        # Dialect / enrichment (from metadata_tagger or scraper)
        "dialect": str,                 # western_armenian | eastern_armenian | mixed | unknown
        "dialect_subcategory": str | None,
        "region": str | None,
        "language_code": str | None,    # hyw, hye, hy, xcl (classical), etc.
        "source_language_codes": list | None,   # from news/RSS catalog when article appears in multiple language feeds
        "source_type": str,
        "source_name": str,
        "content_type": str,
        "writing_category": str | None,  # e.g. news, analysis, diaspora, international (from RSS/news catalog)
        "confidence_dialect": float,
        "confidence_region": float,
        "enrichment_date": str | None,

        # Author placeholders (future)
        "author_region_approximate": str | None,
        "author_dialect_specific_approximate": str | None,

        # Optional: per-document metrics (when compute_metrics_on_ingest is True)
        "document_metrics": {
            "lexical_ttr": float,
            "sentence_count": int,
            "word_count": int,
            "loanwords": dict,          # source_lang -> count
            "possible_loanwords": list,
            "word_counts": dict,         # word -> count (per-doc token counts)
            # ... other TextMetricCard fields
        },
        "drift_check": {                # when drift_check_on_ingest is True and anomaly detected
            "anomalous": True,
            "threshold_sigma": float,
            "alerts": list,
        },

        # Augmentation (when source == "augmented")
        "augmentation_strategy": str | None,
        "source_doc": str | None,
        "paragraph_index": int | None,
        "task_uid": str | None,

        # Source-specific
        "extra": dict,
    },
    "processing": {
        "normalized": bool,
        "deduplicated": bool,
        "filtered": bool,
        "dialect_classified": bool,
    },
}
```

### Indexes

- `(source, 1)`
- `(title, 1)`
- `(metadata.date_scraped, -1)`
- `(processing.deduplicated, 1)`, `(processing.filtered, 1)`
- `(content_hash, 1)` **unique**
- `(normalized_content_hash, 1)`

---

## 2. `catalogs`

Per-source item catalogs (e.g. LOC item IDs, HathiTrust HTIDs). One document per item per source; updated on each run.

### Schema (per item)

```python
{
    "_id": ObjectId,
    "source": str,          # "loc", "hathitrust", "archive_org", "gallica", ...
    "item_id": str,         # LCCN, HTID, identifier, etc.
    "title": str,
    "url": str | None,
    "date": str | None,
    "description": list,
    "subject": list,
    "downloaded": bool,
    "text_extracted": bool,
    "ingested": bool | None,
    "files_downloaded": int | None,
    # HathiTrust: metadata_only, biblio when full text unavailable
    "metadata_only": bool | None,
    "biblio": dict | None,
    "updated_at": datetime,
}
```

### Indexes

- `(source, item_id)` **unique**
- `(source, 1)`

---

## 2b. `news_article_catalog`

RSS-derived catalog: one document per article URL. Used by the news stage to drive full-article scraping and to avoid duplicate full-text documents. Tagged with **language_code**, **source_language_codes**, **content_type**, **writing_category** for filtering.

### Schema (per article URL)

```python
{
    "_id": ObjectId,
    "url": str,
    "title": str,
    "summary": str,
    "published_at": datetime | None,
    "category": str,           # news, analysis, diaspora, international, etc.
    "tags": list,
    "language_code": str,      # primary; hy, hyw, hye, eng, und
    "source_language_codes": list,    # all from feeds that referenced this URL
    "content_type": str,       # "article"
    "writing_category": str,   # same as category
    "sources": list,           # RSS source names
    "feed_urls": list,         # RSS feed URLs
    "document_id": str | None, # _id of representative document in documents
}
```

### Indexes

- `(url, 1)`
- `(document_id, 1)`

See [NEWS_AND_RSS_CATALOG.md](NEWS_AND_RSS_CATALOG.md) for run instructions and tagging details.

---

## 3. `metadata`

Pipeline run metadata (stage, timestamp, details). Used by frequency_aggregator and metadata_tagger to store last-run summary.

### Schema (per entry)

```python
{
    "_id": ObjectId,
    "stage": str,           # "frequency_aggregator", "metadata_tagger", etc.
    "status": str | None,   # "ok", "error"
    "timestamp": datetime,
    "details": dict,        # stage-specific (e.g. total_docs_processed, sources, target_weighted)
}
```

**frequency_aggregator** stores: `total_docs_processed`, `unique_words`, `entries_stored`, `sources`, `nayiri_headwords`; when target-weighted: `target_weighted`, `target_pcts`, `source_doc_counts`, `weights_used`. Replaced via `replace_one` with `{"stage": "frequency_aggregator"}`.

### Indexes

- `(stage, 1)`
- `(timestamp, -1)`

---

## 4. `word_frequencies`

Unified word frequency list built by `scraping/frequency_aggregator.py`. One document per word (or replaced in bulk per run).

### Schema (per word)

```python
{
    "_id": ObjectId,
    "word": str,
    "total_count": float,       # weighted sum
    "source_counts": dict,      # source -> count
    "source_count": int,        # number of sources
    "in_nayiri": bool,
    "rank": int,
}
```

### Indexes

- `word` **unique**
- `(rank, 1)`, `(total_count, -1)`

---

## 5. `word_frequencies_facets`

Per-facet word counts (author, source, dialect, year, region) from `metadata.document_metrics.word_counts`. Built by `scraping/word_frequency_facets.py aggregate`.

### Schema (per facet-value-word)

```python
{
    "_id": ObjectId,
    "facet": str,           # "author" | "source" | "dialect" | "year" | "region"
    "facet_value": str,      # e.g. author name, "western_armenian", "2020"
    "word": str,
    "count": int,
}
```

### Indexes

- `(facet, facet_value, word)` **unique**
- `(facet, word)`, `(word, facet, facet_value)`

---

## 6. `book_inventory`

Book inventory entries (`ingestion/discovery/book_inventory.py`). MongoDB-only; no JSONL fallback.

### Schema

Matches `BookInventoryEntry`: `title`, `title_transliteration`, `authors` (list of `BookAuthor`), `first_publication_year`, `editions`, `content_type`, `language_variant`, `coverage_status`, `estimated_word_count`, `worldcat_oclc`, `loc_control_number`, `isbn_primary`, `archive_org_id`, `source_discovered_from`, `confidence_score`, `tags`, `notes`, `metadata_last_updated`, `data_entry_date`.

### Indexes

- `(title, 1)`, `(coverage_status, 1)`, `(authors.name, 1)`

---

## 7. `author_profiles`

Author profiles for research pipeline (e.g. biography enrichment).

### Schema

- `author_id` (unique), `primary_name`, and other profile fields.

### Indexes

- `(author_id, 1)` **unique**
- `(primary_name, 1)`

---

## 8. `augmentation_checkpoint`

Completed augmentation task UIDs for resume. One document per task.

### Schema

```python
{
    "task_uid": str,
    "timestamp": datetime,
    # ... other fields from TaskResult
}
```

### Indexes

- `(task_uid, 1)` **unique**

---

## 9. `augmentation_metrics`

Batch reports and per-task metric cards from the augmentation pipeline.

### Schema (batch report)

```python
{
    "batch_id": str,
    "strategy_name": str,
    "timestamp": datetime,
    **report,   # strategy-specific metrics
}
```

### Schema (metric card)

```python
{
    "text_id": str,
    "strategy_name": str,
    "timestamp": datetime,
    "card": dict,   # metric card content
}
```

---

## 10. `etymology`

Phase 1 etymology / loanword-origin store: one document per lemma. Populated from Wiktextract/kaikki (Armenian), with optional Nayiri or manual entries. Used for loanword tracking and dictionary lookup. See `linguistics/lexicon/etymology_db.py` and `linguistics/tools/import_etymology_from_wiktextract.py` (run: `python -m linguistics.tools.import_etymology_from_wiktextract`).

### Schema (per lemma)

```python
{
    "lemma": str,              # normalized (NFC, lowercase) for lookup
    "source": str,             # "wiktionary" | "nayiri" | "manual"
    "confidence": float,       # 0–1
    "etymology_text": str | None,
    "relationships": list[str], # e.g. ["borrowed_from_russian", "derived_from_greek"]
    "updated_at": datetime,
    "pos": str | None,         # from Wiktextract
    "raw_head": str | None,    # original headword (truncated)
}
```

### Indexes

- `(lemma, 1)` **unique**
- `(source, 1)`

---

## 11. `dialect_clustering`

Optional; written by `linguistics/dialect/dialect_clustering.py` when `--save-mongodb`. Stores PCA coordinates, DBSCAN labels, and sweep parameters.

### Schema

Documents contain feature vectors, cluster labels, and run parameters (see `linguistics/dialect/dialect_clustering.py`).

---

## 12. GridFS: `source_binaries`

PDF and image files for OCR. Stored in GridFS bucket `source_binaries` (16 MB chunk limit per file).

### Metadata (per file)

- `source`: str (e.g. `mss_nkr`, `gomidas`)
- Optional: `url`, `date`, `identifier`

Access via `MongoDBCorpusClient.upload_source_binary`, `get_source_binary_stream`, `download_source_binary_to_path`, `find_source_binaries`.

---

## Source key alignment

Scrapers use `source` identifiers that should align with `scraping/metadata_tagger.py` SOURCE_METADATA for enrichment:

- `newspaper:aztag`, `newspaper:horizon`, `newspaper:asbarez`
- `eastern_armenian_news:armenpress`, `:a1plus`, `:armtimes`, `:aravot`
- `wikipedia`, `wikipedia_wa`, `wikipedia_ea`, `wikisource`
- `archive_org`, `hathitrust`, `loc`, `gallica`, `dpla`, `gomidas`, `mss_nkr`
- `rss_news`, `english_sources`, `culturax`, `nayiri`

See `scraping/metadata_tagger.py` for the full mapping and dialect/region defaults.

---

## Author placeholders

`metadata.author_region_approximate` and `metadata.author_dialect_specific_approximate` are reserved for future enrichment (e.g. NER + biography lookup). Not yet populated by the pipeline.
