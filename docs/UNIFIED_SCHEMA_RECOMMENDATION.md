# Unified Canonical Schema Recommendation

**Generated:** 2026-03-06  
**Purpose:** Provide a unified schema for migration/unification with the lousardzag project (WesternArmenianLLM → lousardzag).

---

## Executive Summary

### Current State
- **SQLite:** 3 database files detected, but only `data/western_armenian.db` has schema (16 tables, 0 rows)
- **MongoDB:** Configured (`western_armenian_corpus` DB with `documents` and `metadata` collections), but not currently accessible/running
- **Row Counts:** All tables currently empty (migration/ingestion phase pending)

### Migration Context
This project ingests Western Armenian texts from multiple sources (Wikipedia, Wikisource, newspapers, Archive.org, CulturaX, HathiTrust, Library of Congress, Nayiri dictionary) into a centralized database for LLM training. The lousardzag project is referenced as the target system for eventual unification.

---

## 1. Candidate Unified Canonical Schema

### 1.1 Core Entities

#### **`corpus_documents`** (Unified Text Corpus Table)
Consolidates all scraped/ingested text documents from all sources. Replaces multiple source-specific tables (`wikipedia_articles`, `newspaper_articles`, `archive_org_texts`, etc.).

| Field | Type | Description | Nullable | Maps to lousardzag |
|-------|------|-------------|----------|-------------------|
| `document_id` | TEXT (PK) | Unique document identifier (UUID or SHA-based) | NO | `card.id` or `corpus_entry.uid` |
| `source_type` | TEXT | Source category: `wikipedia`, `wikisource`, `newspaper`, `archive_org`, `culturax`, `hathitrust`, `loc`, `nayiri` | NO | `source.system` |
| `source_id` | TEXT | Original source identifier (e.g., `archive_id`, `hathi_id`, `loc_id`) | YES | `source.external_id` |
| `source_name` | TEXT | Specific source name (e.g., "aztag", "horizon", "wikipedia_hyw") | YES | `source.name` |
| `title` | TEXT | Document/article title | YES | `corpus_entry.title` or `card.armenian` |
| `author` | TEXT | Author name(s) if known | YES | `metadata.author` |
| `publication_date` | TEXT | ISO date or partial date (YYYY, YYYY-MM, YYYY-MM-DD) | YES | `metadata.date` |
| `full_text` | TEXT | Complete text content | YES | `corpus_entry.text` or `card.example_sentence` |
| `language_variant` | TEXT | `western_armenian`, `eastern_armenian`, `classical`, `mixed`, `unknown` | YES | `metadata.dialect` |
| `source_url` | TEXT | Original URL/permalink if available | YES | `source.url` |
| `content_sha1` | TEXT | SHA-1 hash of `full_text` for deduplication | YES | `metadata.content_hash` |
| `content_length_chars` | INTEGER | Character count | YES | `metadata.char_count` |
| `scraped_timestamp` | DATETIME | Ingestion timestamp (UTC ISO 8601) | YES | `metadata.ingested_at` |
| `operation_id` | TEXT (FK) | Links to `ingestion_operations.operation_id` | YES | `metadata.batch_id` |
| **Processing Flags** | | | | |
| `is_normalized` | BOOLEAN | Text normalized (Unicode NFC, whitespace cleanup) | NO (default FALSE) | `processing.normalized` |
| `is_deduplicated` | BOOLEAN | Duplicate check passed | NO (default FALSE) | `processing.deduplicated` |
| `is_filtered` | BOOLEAN | Western Armenian filter passed | NO (default FALSE) | `processing.wa_validated` |
| `is_dialect_classified` | BOOLEAN | Dialect classification completed | NO (default FALSE) | `processing.classified` |
| **Source-Specific Fields** (denormalized for flexibility) | | | | |
| `extracted_from_format` | TEXT | For `archive_org`: `djvutxt`, `pdf`, `txt` | YES | `source.format` |
| `source_domain` | TEXT | For `culturax`: originating website domain | YES | `source.domain` |
| `headword` | TEXT | For `nayiri`: dictionary headword | YES | `card.armenian` (if vocabulary entry) |
| `part_of_speech` | TEXT | For `nayiri`: POS tag (noun, verb, adj, etc.) | YES | `card.pos` |
| `definition` | TEXT | For `nayiri`: dictionary definition | YES | `card.english` or `card.explanation` |
| `pronunciation` | TEXT | For `nayiri`: IPA/classical pronunciation guide | YES | `card.pronunciation` |
| `etymology` | TEXT | For `nayiri`: word etymology | YES | `metadata.etymology` |
| `examples` | TEXT | For `nayiri`: usage examples (JSON array of strings) | YES | `card.examples[]` |

**Indexes:**
- `idx_corpus_source_type` on `source_type` (filter by source)
- `idx_corpus_sha1` on `content_sha1` (deduplication)
- `idx_corpus_timestamp` on `scraped_timestamp` (chronological queries)
- `idx_corpus_operation` on `operation_id` (batch tracking)
- `idx_corpus_classification` on `is_filtered`, `is_dialect_classified` (processing status)

---

#### **`dictionary_entries`** (Alternative: Separate Table for Structured Vocabulary)
For Nayiri dictionary entries, could be extracted into a dedicated table for cleaner schema:

| Field | Type | Description | Nullable | Maps to lousardzag |
|-------|------|-------------|----------|-------------------|
| `entry_id` | TEXT (PK) | UUID or `nayiri:{headword}` | NO | `card.id` |
| `headword` | TEXT | Armenian word | NO | `card.armenian` |
| `headword_transliterated` | TEXT | Latin transliteration | YES | `card.transliteration` |
| `pronunciation` | TEXT | IPA or classical pronunciation | YES | `card.pronunciation` |
| `part_of_speech` | TEXT | `noun`, `verb`, `adjective`, etc. | YES | `card.pos` |
| `definition` | TEXT | Primary definition | YES | `card.english` |
| `examples` | TEXT | JSON array of example sentences | YES | `card.examples[]` |
| `etymology` | TEXT | Word origin/etymology | YES | `metadata.etymology` |
| `scraped_timestamp` | DATETIME | Ingestion timestamp (UTC ISO 8601) | YES | `metadata.ingested_at` |
| `content_sha1` | TEXT | Hash for deduplication | YES | `metadata.content_hash` |
| `operation_id` | TEXT (FK) | Links to `ingestion_operations` | YES | `metadata.batch_id` |

**Note:** Could also be stored as `source_type='nayiri'` rows in unified `corpus_documents` with specialized fields.

---

### 1.2 Metadata & Provenance Tables

#### **`ingestion_operations`** (Batch/Pipeline Run Tracking)
Already well-structured. Maps cleanly to lousardzag ingestion tracking.

| Field | Type | Maps to lousardzag |
|-------|------|--------------------|
| `operation_id` | TEXT (PK) | `batch.id` or `pipeline_run.id` |
| `source_type` | TEXT | `batch.source_type` |
| `source_name` | TEXT | `batch.source_name` |
| `operation_timestamp` | DATETIME | `batch.started_at` |
| `status` | TEXT | `batch.status` (`ok`, `error`, `running`) |
| `description` | TEXT | `batch.description` |
| `config_snapshot` | TEXT | `batch.config_json` |
| `error_message` | TEXT | `batch.error_log` |

---

#### **`dedup_records`** (Deduplication Tracking)
Tracks duplicate content hashes. Maps to lousardzag deduplication metadata.

| Field | Type | Maps to lousardzag |
|-------|------|--------------------|
| `dedup_id` | TEXT (PK) | `dedup.id` |
| `source_type` | TEXT | `dedup.source_type` |
| `entry_id` | TEXT | `dedup.original_doc_id` |
| `content_sha1` | TEXT | `dedup.content_hash` |
| `first_seen_timestamp` | DATETIME | `dedup.first_seen` |
| `duplicate_count` | INTEGER | `dedup.duplicate_count` |
| `original_source_name` | TEXT | `dedup.canonical_source` |

---

#### **`data_quality`** (Quality Metrics & Validation Results)
Tracks quality checks (e.g., Armenian character ratio, content length validation, dialect purity).

| Field | Type | Maps to lousardzag |
|-------|------|--------------------|
| `quality_id` | TEXT (PK) | `quality_check.id` |
| `operation_id` | TEXT (FK) | `quality_check.batch_id` |
| `source_type` | TEXT | `quality_check.source_type` |
| `table_name` | TEXT | `quality_check.table_name` |
| `metric_name` | TEXT | `quality_check.metric_name` (e.g., `min_armenian_ratio`, `avg_char_count`) |
| `metric_value` | REAL | `quality_check.value` |
| `check_timestamp` | DATETIME | `quality_check.checked_at` |
| `passed` | BOOLEAN | `quality_check.passed` |

---

#### **`migration_log`** (File Migration History)
Tracks file-to-database migration operations (from `data/raw/*` to database).

| Field | Type | Maps to lousardzag |
|-------|------|--------------------|
| `migration_id` | TEXT (PK) | `migration.id` |
| `source_file` | TEXT | `migration.file_path` |
| `source_type` | TEXT | `migration.source_type` |
| `target_table` | TEXT | `migration.target_table` |
| `record_count` | INTEGER | `migration.records_imported` |
| `migration_timestamp` | DATETIME | `migration.completed_at` |
| `status` | TEXT | `migration.status` (`ok`, `error`) |
| `error_message` | TEXT | `migration.error` |
| `file_deleted` | BOOLEAN | `migration.file_cleaned_up` |
| `file_delete_timestamp` | DATETIME | `migration.cleanup_at` |

---

### 1.3 Training & Corpus Splits

#### **`training_allocations`** (Train/Val/Test Splits)
Tracks how documents are assigned to training splits.

| Field | Type | Maps to lousardzag |
|-------|------|--------------------|
| `allocation_id` | TEXT (PK) | `split_allocation.id` |
| `document_id` | TEXT (FK) | `split_allocation.document_id` → `corpus_documents.document_id` |
| `split_type` | TEXT | `split_allocation.split` (`train`, `val`, `test`, `held_out`) |
| `allocation_timestamp` | DATETIME | `split_allocation.assigned_at` |

---

### 1.4 Process Monitoring (Optional Telemetry Tables)

#### **`process_telemetry`** / **`process_metrics`** / **`process_issues`**
These track scraper health, performance, and errors during ingestion. Can map to lousardzag observability/monitoring system if it has one.

---

## 2. MongoDB Schema (Inferred from Code)

### 2.1 Database: `western_armenian_corpus`

#### Collection: `documents`
Mirrors the SQLite `corpus_documents` table in document-oriented form:

```json
{
  "_id": ObjectId("..."),
  "source": "wikipedia",            // source_type
  "title": "Հայկական Լեռնաշխարհ",
  "text": "Full text content...",
  "content_hash": "sha256:abc123...",
  "metadata": {
    "url": "https://...",
    "author": "Author Name",
    "date_scraped": ISODate("2026-03-06T12:00:00Z"),
    "word_count": 1234,
    "char_count": 8765,
    "publication_date": "1920-05-15",
    "extracted_from_format": "djvutxt",  // source-specific
    "item_id": "archive_org_item_123",
    "source_domain": "aztagdaily.com",
    "language_code": "hyw"
  },
  "processing": {
    "normalized": false,
    "deduplicated": false,
    "filtered": false,
    "dialect_classified": false
  }
}
```

**Indexes (from mongodb_client.py):**
- `("source", ASCENDING)` — filter by source type
- `("title", ASCENDING)` — search by title
- `("metadata.date_scraped", DESCENDING)` — chronological order
- `("processing.deduplicated", ASCENDING)` — processing status
- `("processing.filtered", ASCENDING)` — WA validation status
- `("content_hash", ASCENDING, unique=True)` — deduplication

**Maps to lousardzag:**
- `_id` → `document.id`
- `source` → `source.type`
- `title` → `corpus_entry.title`
- `text` → `corpus_entry.full_text`
- `content_hash` → `metadata.hash`
- `metadata.url` → `source.url`
- `metadata.author` → `metadata.author`
- `metadata.date_scraped` → `metadata.ingested_at`
- `metadata.word_count` / `char_count` → `metadata.stats`
- `processing.*` → `processing_flags.*`

---

#### Collection: `metadata`
Tracks pipeline runs and quality metrics (similar to `ingestion_operations` and `data_quality` tables):

```json
{
  "_id": ObjectId("..."),
  "stage": "scraping",              // "scraping", "cleaning", "filtering", "training"
  "status": "ok",                   // "ok", "error", "running"
  "timestamp": ISODate("2026-03-06T12:00:00Z"),
  "details": {
    "source": "wikipedia",
    "documents_processed": 123,
    "errors": 2,
    "config_snapshot": { ... }
  }
}
```

**Indexes:**
- `("stage", ASCENDING)` — filter by pipeline stage
- `("timestamp", DESCENDING)` — chronological order

**Maps to lousardzag:**
- `_id` → `pipeline_run.id`
- `stage` → `pipeline_run.stage`
- `status` → `pipeline_run.status`
- `timestamp` → `pipeline_run.started_at`
- `details` → `pipeline_run.metadata`

---

## 3. Explicit Field Mappings to lousardzag

### Assumption: lousardzag has structures like:
```python
# lousardzag.models
class Card:
    id: str
    armenian: str            # Armenian word/phrase
    english: str             # English translation
    transliteration: str     # Latin script
    pronunciation: str       # IPA or classical
    pos: str                 # part of speech
    example_sentence: str    # usage example
    examples: List[str]      # multiple examples
    metadata: Dict

class CorpusEntry:
    uid: str
    title: str
    text: str                # full document text
    author: str
    date: str
    source: Source
    processing: ProcessingFlags
    metadata: Dict

class Source:
    system: str              # "wikipedia", "archive_org", etc.
    external_id: str         # original source ID
    name: str                # specific source name
    url: str
    format: str              # "djvutxt", "pdf", etc.
    domain: str              # website domain

class ProcessingFlags:
    normalized: bool
    deduplicated: bool
    wa_validated: bool
    classified: bool
```

---

### 3.1 `corpus_documents` → lousardzag.CorpusEntry

| WesternArmenianLLM Field | lousardzag Field | Notes |
|--------------------------|------------------|-------|
| `document_id` | `CorpusEntry.uid` | Primary key |
| `title` | `CorpusEntry.title` | Document title |
| `full_text` | `CorpusEntry.text` | Full text content |
| `author` | `CorpusEntry.author` | Author name |
| `publication_date` | `CorpusEntry.date` | Publication date |
| `source_type` | `Source.system` | Source category |
| `source_id` | `Source.external_id` | Original source ID |
| `source_name` | `Source.name` | Specific source |
| `source_url` | `Source.url` | URL |
| `extracted_from_format` | `Source.format` | File format |
| `source_domain` | `Source.domain` | Website domain |
| `language_variant` | `CorpusEntry.metadata['dialect']` | Dialect tag |
| `is_normalized` | `ProcessingFlags.normalized` | Text normalized |
| `is_deduplicated` | `ProcessingFlags.deduplicated` | Dedup passed |
| `is_filtered` | `ProcessingFlags.wa_validated` | WA filter passed |
| `is_dialect_classified` | `ProcessingFlags.classified` | Dialect classified |
| `content_sha1` | `CorpusEntry.metadata['content_hash']` | SHA-1 hash |
| `content_length_chars` | `CorpusEntry.metadata['char_count']` | Character count |
| `scraped_timestamp` | `CorpusEntry.metadata['ingested_at']` | Ingestion timestamp |
| `operation_id` | `CorpusEntry.metadata['batch_id']` | Batch/operation ID |

---

### 3.2 `dictionary_entries` (Nayiri) → lousardzag.Card

| WesternArmenianLLM Field | lousardzag Field | Notes |
|--------------------------|------------------|-------|
| `entry_id` | `Card.id` | Primary key |
| `headword` | `Card.armenian` | Armenian word |
| `headword_transliterated` | `Card.transliteration` | Latin script |
| `pronunciation` | `Card.pronunciation` | IPA/classical |
| `part_of_speech` | `Card.pos` | POS tag |
| `definition` | `Card.english` | Primary definition |
| `examples` | `Card.examples[]` | JSON array of examples |
| `etymology` | `Card.metadata['etymology']` | Word origin |
| `scraped_timestamp` | `Card.metadata['created_at']` | Ingestion timestamp |
| `content_sha1` | `Card.metadata['content_hash']` | SHA-1 hash |

---

### 3.3 `ingestion_operations` → lousardzag Pipeline Tracking

| WesternArmenianLLM Field | lousardzag Field | Notes |
|--------------------------|------------------|-------|
| `operation_id` | `PipelineRun.id` or `Batch.id` | Primary key |
| `source_type` | `Batch.source_type` | Source category |
| `source_name` | `Batch.source_name` | Specific source |
| `operation_timestamp` | `PipelineRun.started_at` | Start time |
| `status` | `PipelineRun.status` | `ok`, `error`, `running` |
| `description` | `PipelineRun.description` | Human-readable summary |
| `config_snapshot` | `PipelineRun.config_json` | Config at runtime |
| `error_message` | `PipelineRun.error_log` | Error details |

---

### 3.4 `dedup_records` → lousardzag Deduplication Metadata

| WesternArmenianLLM Field | lousardzag Field | Notes |
|--------------------------|------------------|-------|
| `dedup_id` | `DedupRecord.id` | Primary key |
| `source_type` | `DedupRecord.source_type` | Source category |
| `entry_id` | `DedupRecord.original_doc_id` | First occurrence doc ID |
| `content_sha1` | `DedupRecord.content_hash` | SHA-1 hash |
| `first_seen_timestamp` | `DedupRecord.first_seen` | First ingestion timestamp |
| `duplicate_count` | `DedupRecord.duplicate_count` | # of duplicates found |
| `original_source_name` | `DedupRecord.canonical_source` | Canonical source |

---

## 4. Migration Strategy Recommendations

### 4.1 Short-Term: SQLite → MongoDB Migration
Use the existing `scripts/migrate_to_mongodb.py` script to:
1. Ingest text files from `data/raw/` into MongoDB `documents` collection
2. Extract metadata dynamically using source-specific extractors
3. Preserve processing flags in `processing` subdocument

**Benefit:** MongoDB is already configured and preferred for production scale.

---

### 4.2 Mid-Term: Consolidate Source-Specific Tables into Unified `corpus_documents`
**Problem:** Current schema has 7 source-specific tables (`wikipedia_articles`, `newspaper_articles`, `archive_org_texts`, etc.) with overlapping fields.

**Solution:**
1. Create unified `corpus_documents` table with all common fields + source-specific denormalized fields
2. Migrate existing data with `INSERT INTO corpus_documents SELECT ... FROM wikipedia_articles UNION ALL ...`
3. Add `source_type` discriminator column to filter by source
4. Drop old source-specific tables

**Benefit:** Single table for all corpus queries, simpler joins, easier to add new sources.

---

### 4.3 Long-Term: Export to lousardzag Format
Create a migration script that:
1. Reads from `corpus_documents` (SQLite or MongoDB `documents` collection)
2. Maps fields according to Section 3 mappings
3. Writes to lousardzag's expected format (likely JSON Lines, Parquet, or SQL dump)

**Key Decisions:**
- **Card extraction:** For Nayiri entries, map to `Card` objects. For general corpus, map to `CorpusEntry`.
- **Metadata enrichment:** Add lousardzag-specific metadata fields (e.g., validation scores, quality metrics).
- **ID scheme:** Use deterministic ID generation (e.g., `sha256(source_type + source_id)`) for reproducibility.

---

## 5. Candidate Unified Schema Summary

### Primary Tables
1. **`corpus_documents`** — All text documents from all sources (unified)
2. **`dictionary_entries`** — Nayiri dictionary entries (optional separate table)
3. **`ingestion_operations`** — Pipeline run tracking
4. **`dedup_records`** — Deduplication metadata
5. **`data_quality`** — Quality checks
6. **`migration_log`** — File migration history
7. **`training_allocations`** — Train/val/test splits

### MongoDB Collections
1. **`documents`** — Same as `corpus_documents` (document-oriented)
2. **`metadata`** — Pipeline runs and metrics

### Key Design Principles
- **Source-agnostic schema:** One table/collection for all text sources
- **Denormalized source fields:** Keep source-specific metadata in same row for query performance
- **Processing flags:** Track normalization, deduplication, filtering, classification as boolean columns
- **Content hashing:** SHA-1 of full text for deduplication
- **Batch tracking:** Every ingestion operation linked via `operation_id`
- **ISO timestamps:** All timestamps in UTC ISO 8601 format

---

## 6. Fields Likely to Map to lousardzag Cards/Corpus Metadata

### 6.1 Vocabulary/Card Fields (Nayiri → lousardzag.Card)
- `headword` → `Card.armenian`
- `headword_transliterated` → `Card.transliteration`
- `pronunciation` → `Card.pronunciation`
- `part_of_speech` → `Card.pos`
- `definition` → `Card.english`
- `examples` → `Card.examples[]`
- `etymology` → `Card.metadata['etymology']`

### 6.2 Corpus Entry Fields (All Sources → lousardzag.CorpusEntry)
- `document_id` → `CorpusEntry.uid`
- `title` → `CorpusEntry.title`
- `full_text` → `CorpusEntry.text`
- `author` → `CorpusEntry.author`
- `publication_date` → `CorpusEntry.date`
- `source_type` → `Source.system`
- `source_id` → `Source.external_id`
- `source_name` → `Source.name`
- `source_url` → `Source.url`
- `extracted_from_format` → `Source.format`
- `source_domain` → `Source.domain`
- `language_variant` → `metadata.dialect`

### 6.3 Processing Metadata Fields
- `is_normalized` → `ProcessingFlags.normalized`
- `is_deduplicated` → `ProcessingFlags.deduplicated`
- `is_filtered` → `ProcessingFlags.wa_validated`
- `is_dialect_classified` → `ProcessingFlags.classified`
- `content_sha1` → `metadata.content_hash`
- `content_length_chars` → `metadata.char_count`
- `scraped_timestamp` → `metadata.ingested_at`
- `operation_id` → `metadata.batch_id`

### 6.4 Batch/Pipeline Metadata
- `operation_id` → `PipelineRun.id` or `Batch.id`
- `source_type` → `Batch.source_type`
- `source_name` → `Batch.source_name`
- `operation_timestamp` → `Batch.started_at`
- `status` → `Batch.status`
- `config_snapshot` → `Batch.config_json`
- `error_message` → `Batch.error_log`

---

## 7. Next Steps

1. **Read lousardzag schema documentation** (if available) to confirm field names and structure.
2. **Choose unified approach:** Migrate to unified `corpus_documents` table (recommended) or keep source-specific tables.
3. **Update MongoDB schema** to match unified table structure (or vice versa).
4. **Write ETL script** to transform WesternArmenianLLM data → lousardzag format.
5. **Test migration** with sample data (e.g., first 100 documents from each source).
6. **Validate mappings** by querying both systems and comparing results.

---

**Contact:** For questions about this schema or migration strategy, review the generated exports in `migration_exports/` and consult the `src/database/` module documentation.
