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
| **Extraction** | import_anki_sqlite, validate_contract_alignment, materialize_dialect_views, summarize_unified_documents |

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
