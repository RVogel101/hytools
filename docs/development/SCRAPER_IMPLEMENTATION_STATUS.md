# Data Scraper Implementation Status

**Canonical reference for scraper status in armenian-corpus-core.** Scraping and LOC tooling live in this repo under `scraping/`. For pipeline run order and stage list, see [SCRAPING_RUNNER_AND_LOC.md](../SCRAPING_RUNNER_AND_LOC.md) and [SCRAPING_FOLDER_ANALYSIS.md](../SCRAPING_FOLDER_ANALYSIS.md).

**Last updated:** March 2026

---

## Summary

| Area | Status |
|------|--------|
| **Pipeline** | Unified runner: `python -m scraping.runner run \| status \| list \| dashboard` |
| **Digital libraries** | LOC, HathiTrust, archive_org, Gallica, DPLA — all implemented; catalogs and documents in MongoDB |
| **LOC** | Implemented: adaptive 429/Retry-After, X-RateLimit handling, parallel metadata fetch, MongoDB-only, `catalog --full \| --clean \| --status`, `status` from `data/logs/loc_background_errors.log` |
| **HathiTrust** | Implemented; catalog + Bibliographic API fallback in MongoDB. 403 on public search; use Hathifiles/seed list or HTRC bulk when available |
| **Other sources** | Wikipedia (WA/EA), Wikisource, newspaper, ea_news, rss_news, culturax, english_sources, nayiri, gomidas, ocr_ingest, mss_nkr; mechitarist/agbu stubs (partnership required) |
| **Post-processing** | metadata_tagger, frequency_aggregator, word_frequency_facets (multi-dimensional + target-weighted); cleaning via `cleaning.run_mongodb` |
| **Extraction** | import_anki_to_mongodb, validate_contract_alignment, materialize_dialect_views, summarize_unified_documents |

---

## Implemented Scrapers (high level)

### Library of Congress (LOC)

- **Module:** `scraping/loc.py`
- **Status:** Implemented, MongoDB-only
- **Features:** LOC JSON search API; item metadata in batches (ThreadPoolExecutor, pool 3, batch 6); text extraction; adaptive rate limiting (429 → Retry-After, 503 exponential backoff, X-RateLimit-*); WA filter via `insert_or_skip`; config passed for metrics/drift when enabled
- **Catalog:** MongoDB (no `loc_catalog.json`); `catalog --full`, `catalog --clean`, `catalog --status`
- **Progress:** `python -m scraping.loc status` reads `data/logs/loc_background_errors.log`
- **Background:** `python -m scraping.loc run --background`

### HathiTrust

- **Module:** `scraping/hathitrust.py`
- **Status:** Implemented; catalog + Bibliographic API fallback when full text unavailable; stub `load_htrc_bulk()` for HTRC bulk
- **Note:** 403 on public search; use Hathifiles/seed list or HTRC research dataset for bulk access

### Other digital libraries

- **archive_org:** Catalog in MongoDB; `catalog --refresh`, `--rebuild`, `--add-queries`
- **Gallica:** SRU API; catalog refresh; MongoDB-only. See [DATA_SOURCES_API_REFERENCE.md](../DATA_SOURCES_API_REFERENCE.md)
- **DPLA:** REST v2; API key required; implemented in `scraping/dpla.py`. See [DATA_SOURCES_API_REFERENCE.md](../DATA_SOURCES_API_REFERENCE.md)

### News (newspapers, RSS, Eastern Armenian)

- **Diaspora newspapers (Aztag, Horizon, Asbarez):** `ingestion.acquisition.news`; Selenium-based. **Asbarez (asbarez.com):** If requests fail or pages do not load, try disabling VPN; the site may block or throttle VPN IPs. (Needs verification.)
- **RSS news:** Single process when `populate_catalog` is true (default): (1) Update **news_article_catalog** from all RSS feeds — one catalog document per article URL, with `sources` and `feed_urls` arrays when the same URL appears in multiple feeds. Catalog and resulting documents are tagged with **language_code**, **source_language_codes**, **content_type** (`article`), and **writing_category** (e.g. news, analysis, diaspora, international). (2) For each catalog entry without a `document_id`, fetch full article, insert into **documents** (standard enrichment runs), and set `catalog.document_id` to the representative document. No duplicate full articles; catalog holds a meta link to the document. See [NEWS_AND_RSS_CATALOG.md](../concept_guides/NEWS_AND_RSS_CATALOG.md) for schema, tagging, and run instructions.

### Wikimedia, news, datasets, reference

- **wikipedia_wa / wikipedia_ea / wikisource:** Stream or API → MongoDB
- **newspaper, ea_news, rss_news:** Run then ingest; some stages still write checkpoint files (JSONL/txt) before MongoDB
- **culturax, english_sources, nayiri, mss_nkr:** Implemented; some write intermediate files
- **gomidas:** PDF → OCR (temp) → MongoDB
- **ocr_ingest:** Temp dirs only; scans config path (e.g. `data/raw`)
- **mechitarist, agbu:** Stubs; require catalog_path or API when access granted. See [DATA_SOURCES_API_REFERENCE.md](../DATA_SOURCES_API_REFERENCE.md)

---

## Configuration and runner

- **Config:** `config/settings.yaml` (or `--config`); `scraping.<stage>` and `database.*` keys. Defaults in `scraping.runner._default_scraping_config()`.
- **Stages:** `python -m scraping.runner list` — all stages with module and MongoDB support.
- **Dashboard:** `python -m scraping.runner dashboard --output data/logs/scraper_dashboard.html` — document counts by source, word frequency entries, last run summary.
- **Implementation history:** Implemented features (metrics, drift, word frequencies, LOC, etc.) are recorded in [IMPLEMENTATION_HISTORY.md](../IMPLEMENTATION_HISTORY.md).

---

## Eastern Armenian news (reliability)

- **Scope:** ea_news fallback listing-page crawling and safer feed handling (armenpress, armtimes).
- **Tests:** `tests/test_eastern_armenian_news.py` — update imports to `scraping.ea_news` (flat package; no `armenian_corpus_core.scraping.news.ea_news`).
- **Metadata tests:** Update to `scraping.metadata_tagger` (no `postprocessing` subpackage). See [SCRAPING_FOLDER_ANALYSIS.md](../SCRAPING_FOLDER_ANALYSIS.md) § Breakages.

---

## References

- [SCRAPING_RUNNER_AND_LOC.md](../SCRAPING_RUNNER_AND_LOC.md) — Runner design, LOC as stage, background modes, stage names
- [SCRAPING_FOLDER_ANALYSIS.md](../SCRAPING_FOLDER_ANALYSIS.md) — Per-module analysis, MongoDB status, tests, config keys
- [DATA_SOURCES_API_REFERENCE.md](../DATA_SOURCES_API_REFERENCE.md) — Gallica, DPLA, Gomidas, Mechitarist, AGBU APIs and config
- [FUTURE_IMPROVEMENTS.md](../FUTURE_IMPROVEMENTS.md) — New sources, HathiTrust bulk, session carry-forward
- [IMPLEMENTATION_HISTORY.md](../IMPLEMENTATION_HISTORY.md) — Implemented features audit

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
# Scraping Runner and LOC Design

## Architecture Overview

The scraping pipeline is **centralized** in `scraping.runner`. All data-acquisition and processing stages run sequentially through this single entry point:

- **Wikimedia**: wikipedia_wa, wikipedia_ea, wikisource  
- **Digital libraries**: archive_org, hathitrust, gallica, **loc**, **dpla**  
- **News**: newspaper, ea_news, rss_news  
- **Datasets**: culturax, english_sources  
- **Reference**: nayiri, gomidas, **mechitarist**, **agbu**, ocr_ingest, mss_nkr, worldcat_searcher  
- **Post-processing**: **cleaning** (cleaning.run_mongodb), metadata_tagger, frequency_aggregator  
- **Extraction**: import_anki_to_mongodb, validate_contract_alignment, materialize_dialect_views, summarize_unified_documents  

**CLI:** `python -m scraping.runner run | status | list | dashboard`

## Why LOC Is in the Runner

LOC is a **normal stage** in the pipeline, alongside archive_org, hathitrust, and gallica. It is not a separate "background" process by design:

- **Same contract**: LOC has `run(config)` like other scrapers
- **Same runner**: `python -m scraping.runner run` runs LOC when the `loc` stage is enabled
- **MongoDB-only**: LOC writes to MongoDB; no local JSON/txt storage

LOC is included because it is one of the primary digital library sources for Western Armenian texts.

## Background Modes

Two levels of background execution exist:

### 1. Full pipeline in background

```bash
python -m scraping.runner run --background
```

Runs the entire pipeline (including LOC) in a detached process. Logs go to `data/logs/pipeline_runner.log`.

### 2. LOC-only in background

```bash
python -m scraping.loc run --background
```

Runs the LOC stage alone in background. Useful when you want to:

- Run only LOC scraping without other stages
- Use LOC's separate CLI (`catalog`, `status`, `clean`)

LOC has its own CLI because it has special needs:

- **catalog**: Manage catalog in MongoDB (clean malformed IDs, show status)
- **status**: Show progress from log files
- **catalog --clean**: Filter invalid item IDs

## Centralization

Background processes are **centralized** in the runner:

- **Full pipeline background**: Use `scraping.runner run --background`
- **Single-stage background**: Use `scraping.<stage> run --background` (e.g. LOC)

Both spawn the same underlying process; the runner just orchestrates all stages. For CI, cron, or systemd, prefer the runner:

```bash
python -m scraping.runner run --background
```

## Stage Names

Stage names for `--only` and `--skip` (and `--group` when used) match the runner’s `_build_stages()`:

- **Wikimedia:** wikipedia_wa, wikipedia_ea, wikisource  
- **Digital libraries:** archive_org, hathitrust, gallica, loc, dpla  
- **News:** newspaper, ea_news, rss_news  
- **Datasets:** culturax, english_sources  
- **Reference:** nayiri, gomidas, mechitarist, agbu, ocr_ingest, mss_nkr, worldcat_searcher  
- **Post-processing:** cleaning, metadata_tagger, frequency_aggregator, export_corpus_overlap_fingerprints  
- **Extraction:** import_anki_to_mongodb, validate_contract_alignment, materialize_dialect_views, summarize_unified_documents  

**Dashboard:** `python -m scraping.runner dashboard [--output data/logs/scraper_dashboard.html]` generates static HTML with document counts by source and word frequency summary. Requires MongoDB.

For CI, cron, or systemd, prefer the full runner; use `--group scraping`, `--group extraction`, or `--group postprocessing` to run predefined stage subsets (see `runner.py` for the exact list per group).
