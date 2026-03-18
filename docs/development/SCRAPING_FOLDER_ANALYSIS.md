# Scraping Folder — Full In-Depth Analysis

**Date**: March 2026  
**Scope**: `scraping/` directory (35 Python files), pipeline runner, cleaning stage, MongoDB integration

---

## 1. Executive Summary

| Metric | Status |
|--------|--------|
| **Total modules** | 35 |
| **Pipeline stages** | 26 (21 with `run()`, 3 with `main()` only, 2 run+main) |
| **MongoDB-integrated** | 22+ stages |
| **MongoDB-only (no JSON/txt)** | loc, HathiTrust, Gallica, Gomidas, DPLA, archive_org, ocr_ingest, metadata_tagger, frequency_aggregator, materialize_dialect_views, summarize_unified_documents, etc. |
| **Still writing JSON/txt** | ea_news, newspaper, nayiri, rss_news, english_sources, culturax, mss_nkr (checkpoints/downloads); _helpers (download_dump for Wikipedia) |
| **Tests** | test_registry, test_mappers pass; test_eastern_armenian_news / test_metadata_tagging need import path fixes (scraping.* flat) |
| **Runner** | `run`, `status`, `list`, `dashboard`; --only, --skip, --group scraping|extraction|postprocessing |

---

## 2. Pipeline Architecture

### Run Order (from `runner.py`)

1. **Wikimedia**: wikipedia_wa → wikipedia_ea → wikisource  
2. **Digital libraries**: archive_org → hathitrust → gallica → loc → dpla  
3. **News**: newspaper → ea_news → rss_news  
4. **Datasets**: culturax → english_sources  
5. **Reference**: nayiri → gomidas → mechitarist → agbu → ocr_ingest → mss_nkr  
6. **Standalone**: worldcat_searcher (has_main only)  
7. **Post-processing**: cleaning (cleaning.run_mongodb) → metadata_tagger → frequency_aggregator → export_corpus_overlap_fingerprints  
8. **Extraction**: import_anki_to_mongodb → validate_contract_alignment → materialize_dialect_views → summarize_unified_documents  

### Stage Invocation

- **`run(config)`**: Most stages; runner passes `config` dict.  
- **`main()`**: worldcat_searcher, import_anki_to_mongodb; export_corpus_overlap_fingerprints and validate_contract_alignment have both.  
- **materialize_dialect_views**, **summarize_unified_documents**: `run()` only.

---

## 3. Per-Module Analysis

### 3.1 Digital Libraries (MongoDB-only)

| Module | Status | MongoDB | File Persistence | Notes |
|--------|--------|--------|------------------|-------|
| **loc** | ✅ Complete | ✅ | ❌ (error log only) | `catalog --full`, `--clean`, `--status`; 429/503/Retry-After; parallel metadata batches; status from `data/logs/loc_background_errors.log` |
| **archive_org** | ✅ Complete | ✅ | ❌ | Catalog in MongoDB; `catalog --refresh`, `--rebuild`, `--add-queries` |
| **hathitrust** | ✅ Complete | ✅ | ❌ | Catalog + Bibliographic API fallback; 403 on search; Hathifiles/HTRC bulk stub |
| **gallica** | ✅ Complete | ✅ | ❌ | SRU API; `catalog --status`, `--refresh` |
| **dpla** | ✅ Complete | ✅ | ❌ | REST v2; API key required; see DATA_SOURCES_API_REFERENCE.md |
| **gomidas** | ✅ Complete | ✅ | ❌ | PDF→OCR in temp; inserts to MongoDB |

### 3.2 Wikimedia (MongoDB-native)

| Module | Status | MongoDB | File Persistence | Tests | Notes |
|--------|--------|--------|------------------|-------|-------|
| **wikipedia_wa** | ✅ Complete | ✅ | ⚠️ Dump download | ❌ | Streams bz2 → MongoDB; keeps dump for resume |
| **wikipedia_ea** | ✅ Complete | ✅ | ⚠️ Dump download | ❌ | Same pattern |
| **wikisource** | ✅ Complete | ✅ | ❌ | ❌ | MediaWiki API → MongoDB only |

### 3.3 News (Still writing files)

| Module | Status | MongoDB | File Persistence | Tests | Notes |
|--------|--------|--------|------------------|-------|-------|
| **ea_news** | ⚠️ Partial | ✅ | ✅ `.txt` + `_metadata.jsonl` | ❌ (import fail) | Writes to `data/raw/news_ea/`; then ingests from files |
| **newspaper** | ⚠️ Partial | ✅ | ✅ JSONL checkpoint + `.txt` | ❌ | Selenium; JSONL for resume |
| **rss_news** | ⚠️ Partial | ✅ | ✅ JSONL | ❌ | Writes JSONL; then ingests |

### 3.4 Datasets / Reference

| Module | Status | MongoDB | File Persistence | Tests | Notes |
|--------|--------|--------|------------------|-------|-------|
| **culturax** | ⚠️ Partial | ✅ | ✅ JSON stats | ❌ | HuggingFace gated; writes `processed/written` JSON |
| **english_sources** | ⚠️ Partial | ✅ | ✅ JSONL | ❌ | Writes JSONL; then ingests |
| **nayiri** | ⚠️ Partial | ✅ | ✅ JSON + JSONL | ❌ | Dictionary; multiple JSON outputs |
| **mss_nkr** | ⚠️ Partial | ✅ | ✅ Catalog JSON + downloads | ❌ | Downloads to disk; catalog JSON; ingests .txt/.html |
| **ocr_ingest** | ✅ Complete | ✅ | ❌ (temp only) | ❌ | Uses `tempfile.TemporaryDirectory` for OCR |

### 3.5 Post-Processing / Extraction (MongoDB-native)

| Module | Status | MongoDB | File Persistence | Notes |
|--------|--------|--------|------------------|-------|
| **cleaning** | ✅ | ✅ | — | `cleaning.run_mongodb`; enabled via `scraping.cleaning` |
| **metadata_tagger** | ✅ Complete | ✅ | ❌ | Batch enrichment |
| **frequency_aggregator** | ✅ Complete | ✅ | ❌ | Word frequency; target-weighted config supported |
| **word_frequency_facets** | ✅ Complete | ✅ | ❌ | Multi-dimensional facets (author, source, dialect, year, region); aggregate/query CLI |
| **export_corpus_overlap_fingerprints** | ✅ Complete | ✅ | ❌ | main() or run |
| **import_anki_to_mongodb** | ✅ Complete | ✅ | ❌ | Reads AnkiConnect, inserts to MongoDB |
| **validate_contract_alignment** | ✅ Complete | ✅ | ❌ | Validates corpus |
| **materialize_dialect_views** | ✅ Complete | ✅ | ❌ | Dialect tagging |
| **summarize_unified_documents** | ✅ Complete | ✅ | ❌ | Summary stats |

### 3.6 Standalone / Utilities

| Module | Status | MongoDB | File Persistence | Notes |
|--------|--------|--------|------------------|-------|
| **worldcat_searcher** | ⚠️ | ❌ | ❌ | Imports `ingestion.discovery.book_inventory`; catalog search only; has_main, no run() |
| **_helpers** | ✅ | ✅ | ⚠️ `download_dump` | `load_catalog_from_mongodb`, `save_catalog_to_mongodb`, `insert_or_skip` (metrics/drift when config enabled) |
| **runner** | ✅ | — | ✅ PID + summary JSON | `pipeline_summary.json`, `.pipeline_runner.pid`; commands: run, status, list, dashboard |

---

## 4. MongoDB Integration Status

### Fully MongoDB-only (no data files)

- **loc**, **archive_org**, **hathitrust**, **gallica**, **dpla**, **gomidas** — catalog + documents in MongoDB  
- **wikipedia_wa**, **wikipedia_ea**, **wikisource** — stream to MongoDB (dumps kept for resume)  
- **ocr_ingest** — temp dirs only  
- **metadata_tagger**, **frequency_aggregator**, **word_frequency_facets**, **materialize_dialect_views**, **summarize_unified_documents** — read/write MongoDB only  
- **import_anki_to_mongodb** — reads AnkiConnect, writes MongoDB  
- **validate_contract_alignment**, **export_corpus_overlap_fingerprints** — MongoDB only  
- **mechitarist**, **agbu** — stubs; when configured, catalog/API → MongoDB

### Still writing to disk (minimal)

| Module | Files written | Purpose |
|--------|---------------|---------|
| **mss_nkr** | Downloads only (PDFs/images) | Catalog now in MongoDB |
| **_helpers** | — | `download_dump` writes bz2 (Wikipedia source) |

---

## 5. Test Coverage

### Tests that touch scraping

| Test file | Status | Details |
|-----------|--------|---------|
| **test_registry** | ✅ PASS | 15 tests; `scraping.registry` |
| **test_mappers** | ✅ PASS | 25 tests; `scraping.mappers` |
| **test_eastern_armenian_news** | ❌ FAIL | `ModuleNotFoundError: armenian_corpus_core`; expects `armenian_corpus_core.scraping.news.ea_news` |
| **test_metadata_tagging** | ❌ FAIL | `ModuleNotFoundError: armenian_corpus_core`; expects `armenian_corpus_core.scraping.metadata`, `armenian_corpus_core.scraping.postprocessing.metadata_tagger` |

### No tests for

- loc, archive_org, hathitrust, gallica, gomidas
- wikipedia_wa, wikipedia_ea, wikisource
- newspaper, rss_news, english_sources, culturax, nayiri, mss_nkr
- ocr_ingest
- metadata_tagger, frequency_aggregator, materialize_dialect_views, summarize_unified_documents
- import_anki_to_mongodb, validate_contract_alignment, export_corpus_overlap_fingerprints
- runner

### `test_worldcat_searcher`

- Tests `ingestion.discovery.worldcat_searcher` (in `ingestion/discovery/`), not `scraping.worldcat_searcher`
- `ingestion/discovery/worldcat_searcher.py` imports `ingestion.discovery.book_inventory` — same package

---

## 6. Breakages and Risks

### 6.1 Import path mismatches

- **test_eastern_armenian_news**: Expects `armenian_corpus_core.scraping.news.ea_news`; actual module is `scraping.ea_news` (flat).
- **test_metadata_tagging**: Expects `armenian_corpus_core.scraping.metadata` and `armenian_corpus_core.scraping.postprocessing.metadata_tagger`; actual module is `scraping.metadata_tagger` (no `postprocessing` subpackage).

### 6.2 worldcat_searcher

- **Import**: `from ingestion.discovery.book_inventory import ...` (research moved under ingestion).
- **Runner**: `has_run=False`, `has_main=True` — invokes `main()` when stage runs; used for book inventory discovery, not document ingestion.
- **MongoDB**: Does not write to corpus MongoDB; separate book-inventory workflow.

### 6.3 ocr_ingest runner integration

- **Runner**: `ocr_ingest` has `run(config)` with optional `path`; runner calls `mod.run(cfg)`.
- **Config**: `config.get("paths", {}).get("raw_dir", "data/raw")` — `ocr_ingest` scans `data/raw` by default.
- **No `--path`** passed from runner; config must set `scraping.ocr_ingest.path` if needed.

### 6.4 mss_nkr

- **Fixed**: `prog` now correctly references `scraping.mss_nkr`.
- **Catalog**: Migrated to MongoDB (`mss_nkr_catalog` source).

---

## 7. Feature Completeness

### High (production-ready)

- **loc**: Full catalog (MongoDB), clean, status from `loc_background_errors.log`, parallel metadata, adaptive rate limiting, MongoDB-only  
- **archive_org**, **hathitrust**, **gallica**, **dpla**, **gomidas**: MongoDB-only  
- **wikipedia_wa**, **wikipedia_ea**, **wikisource**: MongoDB-only  
- **metadata_tagger**, **frequency_aggregator**, **word_frequency_facets**, **materialize_dialect_views**, **summarize_unified_documents**  
- **import_anki_to_mongodb**, **validate_contract_alignment**, **export_corpus_overlap_fingerprints**  
- **runner**: run, status, list, dashboard; --only, --skip, --group

### Medium (works but writes files)

- **ea_news**: Works; writes .txt + metadata.jsonl
- **newspaper**: Works; Selenium + JSONL; writes .txt
- **rss_news**: Works; writes JSONL
- **english_sources**: Works; writes JSONL
- **culturax**: Works; HuggingFace gated; writes JSON
- **nayiri**: Works; writes JSON/JSONL
- **mss_nkr**: Works; writes catalog + downloads

### Low (blocked or incomplete)

- **hathitrust**: 403 on search; Hathifiles + seed list work
- **worldcat_searcher**: No MongoDB; catalog search only; `main()` not wired for runner

---

## 8. Logging

### Structured logging (added)

- **loc**, **hathitrust**, **gallica**, **gomidas**, **archive_org**: `log_stage`, `log_item` with stage, item_id, action, status, duration_ms, error
- **LOC**: `data/logs/loc_api_errors.jsonl` for 503/404

### Minimal logging

- **ea_news**, **newspaper**, **rss_news**, **english_sources**, **nayiri**, **culturax**, **mss_nkr**: Standard `logger.info`/`debug`/`warning`

---

## 9. Recommendations

### High priority

1. **Fix test imports**: Update `test_eastern_armenian_news` and `test_metadata_tagging` to use `scraping.ea_news` and `scraping.metadata_tagger` (and correct `metadata` path).
2. **MongoDB-only for remaining scrapers**: Refactor ea_news, newspaper, rss_news, english_sources, nayiri, culturax, mss_nkr to stream to MongoDB without writing JSON/txt.
3. **mss_nkr**: Migrate catalog to MongoDB; fix `main()` module path.

### Medium priority

4. **Add tests**: Unit tests for loc, archive_org, gallica, hathitrust, gomidas (with mocks for HTTP).
5. **worldcat_searcher**: Clarify role (catalog vs ingestion); add MongoDB write if desired; fix runner integration.
6. **ocr_ingest**: Add `scraping.ocr_ingest.path` config support in runner.

### Low priority

7. **Wikipedia dumps**: Keep bz2 for resume; consider streaming-only if disk is a concern.
8. **Documentation**: Per-module docstrings with usage, config keys, and MongoDB schema.

---

## 10. File Inventory

```
scraping/
├── __init__.py
├── _helpers.py              # MongoDB, WA classifier, insert_or_skip, catalog I/O
├── runner.py                # Pipeline orchestration (run, status, list, dashboard)
├── archive_org.py           # Internet Archive ✅
├── gallica.py               # Gallica/BnF ✅
├── dpla.py                  # DPLA (API key) ✅
├── gomidas.py               # Gomidas Institute ✅
├── hathitrust.py            # HathiTrust ✅
├── loc.py                   # Library of Congress ✅
├── wikipedia_wa.py          # Wikipedia hyw ✅
├── wikipedia_ea.py          # Wikipedia hy ✅
├── wikisource.py            # Wikisource ✅
├── ea_news.py               # Eastern Armenian news ⚠️
├── newspaper.py             # Diaspora newspapers ⚠️
├── rss_news.py              # RSS feeds ⚠️
├── culturax.py              # CulturaX HuggingFace ⚠️
├── english_sources.py       # English sources ⚠️
├── nayiri.py                # Nayiri dictionary ⚠️
├── mss_nkr.py               # MSS NKR archive ⚠️
├── mechitarist.py           # Mechitarist (stub) ⚠️
├── agbu.py                  # AGBU Nubar (stub) ⚠️
├── ocr_ingest.py            # OCR pipeline ✅
├── metadata_tagger.py       # Metadata enrichment ✅
├── frequency_aggregator.py  # Word frequency ✅
├── word_frequency_facets.py # Multi-dimensional facets ✅
├── materialize_dialect_views.py
├── summarize_unified_documents.py
├── export_corpus_overlap_fingerprints.py
├── import_anki_to_mongodb.py
├── validate_contract_alignment.py
├── worldcat_searcher.py     # WorldCat (catalog only)
├── metadata.py
├── mappers.py
├── data_sources.py
└── registry.py
```

---

## 11. Config Keys (from `_default_scraping_config`)

```yaml
scraping:
  wikipedia: {}
  wikisource: {}
  archive_org: {}
  hathitrust: {}
  gallica: {}
  loc: {}
  dpla: {}
  newspapers: {}
  eastern_armenian: {}
  rss_news: {}
  culturax: {}
  english_sources: {}
  worldcat: {}
  metadata_tagger: {}
  frequency_aggregator: {}
  export_corpus_overlap_fingerprints: {}
  extraction: {}
  ocr_ingest: {}
  gomidas: {}
  mechitarist: {}
  agbu: {}
  mss_nkr: {}
  cleaning: {}
```

---

*End of analysis*
