# Data Sources, APIs, and Persistence (armenian-corpus-core)

Central reference for:
- **Data persistence and file usage** (local vs MongoDB, zero-local-storage config)
- **External data sources & APIs** (Gallica, DPLA, Gomidas, Mechitarist, AGBU, etc.)
- **Data source expansion plan** (HathiTrust, LOC, EAP, NLA, university archives, etc.)

Implemented features are also summarized in `docs/development/FUTURE_IMPROVEMENTS.md` and `docs/development/SCRAPER_IMPLEMENTATION_STATUS.md`.

---

## Summary table (high-level status)

| Area / Topic                          | Status              | Priority      | Summary / Next steps                                                                                   |
|--------------------------------------|---------------------|---------------|--------------------------------------------------------------------------------------------------------|
| Data persistence & zero local storage| ✅ Implemented       | High          | All core pipelines can run MongoDB-only; local files are optional & deletable after ingest/OCR.       |
| Wikipedia & file-based raw inputs    | ✅ Implemented       | Medium        | Wikipedia bz2 + OCR sources used only during runs; can be deleted post-ingest with `delete_after_ingest`. |
| Book inventory & author profiles     | ✅ In MongoDB        | Medium        | JSONL considered legacy; use `migrate_book_inventory_to_mongodb.py` and Mongo collections going forward. |
| Gallica API integration              | ✅ Implemented       | Medium        | SRU-based scraper live (`scraping/gallica.py`); see API details + config below.                        |
| DPLA API integration                 | ✅ Implemented       | Medium        | REST v2 scraper live (`scraping/dpla.py`); API key required; see request & config details.             |
| Gomidas Institute scraper            | ✅ Implemented       | Medium        | HTML+PDF+OCR scraper live (`scraping/gomidas.py`); bulk permission template ready.                     |
| Mechitarist (Venice) stub            | ⏳ Stub, needs access| Medium/Long   | `scraping/mechitarist.py` ready; requires catalog export or API + permission (see request template).   |
| AGBU Nubar Library stub              | ⏳ Stub, needs access| Medium/Long   | `scraping/agbu.py` ready; requires partnership/export; email draft in requests_guides.                 |
| HathiTrust integration               | ⚠️ Partially blocked | Medium        | Scraper exists; search blocked (403); use Hathifiles / HTRC dataset request for large-scale use.       |
| Library of Congress integration      | ✅ Catalog; downloads slow | Medium | 1,220 items cataloged; download phase slow/503-prone; needs long-running runs + `catalog --clean`.    |
| Data sources expansion plan          | ✅ Documented        | Medium/Long   | Detailed tiered plan plus research on EAP, NLA, CFWAS, universities, etc.; see sections below.         |

---

## 1. Data Persistence and File Usage

_Source: merged from `DATA_PERSISTENCE_AND_FILE_USAGE.md`._

### Book Inventory and MongoDB

**Does the book inventory load to and live in MongoDB at the end of the process?**

**Yes.** When `config` has `database.mongodb_uri`, `BookInventoryManager` loads from and saves to the `book_inventory` MongoDB collection. Use `python -m ingestion.discovery.migrate_book_inventory` to migrate existing JSONL. JSONL is fallback when MongoDB is not configured.

---

### Exclusion Lists: Western (Classical) + Eastern + Latin

**Yes.** All three lists include Western Armenian with proper classical spelling:

| List | WA (classical) | EA (reformed) | Latin |
|------|----------------|---------------|-------|
| **Book-of patterns** | Պատմութիւն, Տաղերգութիւն (իւ, ւ) | Պատմություն, Տաղերգություն (յու) | — |
| **Exclusion places** | Պէյրութ, Պոլիս, Փարիզ, Հալէպ, Երեւան, Մոնթրէալ, Նիւ Եորք | Բեյրութ, Երևան, Նյու Յորք | peyrouth, beirut, bolis, etc. |
| **Exclusion institutions** | Մխիթարեան, Նուպարեան (եան) | Մխիթարյան, Նուպարյան (արյան) | mekhitarean, nubarean |

---

### File Usage: Why Saved, Used For, Cost/Benefit, Can Delete?

#### Wikipedia dumps — bz2 files

| | |
|--|--|
| **Path** | `data/raw/wikipedia_*/hywiki-*-pages-articles.xml.bz2` |
| **Why saved** | Downloaded once from Wikimedia; kept for resume and re-runs. |
| **Used for** | Streaming XML parse → extract article text → ingest to MongoDB. |
| **Size** | ~100MB–1GB+ per dump. |
| **Local vs MongoDB** | MongoDB: Poor fit. Binary blobs (GridFS) add overhead; bz2 is a stream, not a document. Storing raw XML in MongoDB is wasteful. |
| **Cost (local)** | Disk space; must re-download if deleted. |
| **Benefit (local)** | Resume without re-download; re-run extraction without network. |
| **Can delete?** | **Yes, after ingest.** If extraction is complete and you do not need resume, delete the bz2. Re-download when you need a fresh dump. |

---

#### mss_nkr — PDFs/images

| | |
|--|--|
| **Path** | `data/raw/mss_nkr/` |
| **Why saved** | Downloaded from remote; OCR needs local file path. |
| **Used for** | Tesseract OCR reads PDFs/images → text → ingest to MongoDB. |
| **Size** | Variable (MB–GB). |
| **Local vs MongoDB** | MongoDB GridFS can store binaries, but OCR tools (Tesseract) expect local paths. Streaming from MongoDB to temp file adds complexity. |
| **Cost (local)** | Disk space. |
| **Benefit (local)** | OCR requires file path; re-download is costly if source is slow. |
| **Can delete?** | **Yes, after OCR.** Once text is in MongoDB, delete PDFs/images. Re-download only if you need to re-OCR (e.g. better model). |

---

#### archive_org, gomidas — catalogs (MongoDB-native)

| | |
|--|--|
| **Path** | _None_ (no JSON catalogs on disk in current pipeline) |
| **Why saved** | Catalogs now live in MongoDB via `load_catalog_from_mongodb` / `save_catalog_to_mongodb` (see `scraping._helpers`). |
| **Used for** | Resume crawl; inspect catalog (`catalog_status_mongo`); feed ingest. Extracted text goes to MongoDB `documents`. |
| **Size** | Typically MB, not GB. |
| **Local vs MongoDB** | **MongoDB: Good fit.** Implemented; catalogs are stored in the `catalogs` collection keyed by source (`archive_org`, `loc`, `hathitrust`, `gallica`, etc.). |
| **Cost (local)** | None for catalogs; only logs in `data/logs`. |
| **Benefit (local)** | N/A for catalogs (MongoDB only). |
| **Can delete?** | Yes — any legacy `data/raw/archive_org/` / `data/raw/gomidas/` JSON catalogs from older runs can be deleted once migrated. |

---

#### ocr_ingest — OCR input (PDFs/images)

| | |
|--|--|
| **Path** | `data/raw/` (e.g. `data/raw/gomidas/`, `data/raw/mss_nkr/`) |
| **Why saved** | OCR pipeline reads from local paths. |
| **Used for** | Same as mss_nkr — Tesseract needs file paths. |
| **Can delete?** | **Yes, after OCR.** Same as mss_nkr. |

---

#### Augmentation — output and checkpoint (MongoDB backend)

| | |
|--|--|
| **Path** | _None_ when `augmentation.output_backend: "mongodb"` and `source_backend: "mongodb"` (recommended, and set in default config). |
| **Why saved** | Augmented paragraphs and checkpoints are stored directly in MongoDB collections (`documents` with `source: augmented`, plus `augmentation_checkpoint`). |
| **Used for** | Resume interrupted runs; training data export; audit. |
| **Local vs MongoDB** | **MongoDB: Implemented.** File-based `data/augmented/` is no longer required unless explicitly configured. |
| **Cost (local)** | None in default config. |
| **Benefit (local)** | Only if a file-based backend is explicitly requested (not recommended). |
| **Can delete?** | Yes — any legacy `data/augmented/` files from old runs can be deleted once confirmed migrated to MongoDB. |

---

#### Legacy file-based cleaning

| | |
|--|--|
| **Path** | `data/raw/**`, `data/cleaned`, `data/deduped`, `data/filtered` |
| **Why saved** | Legacy pipeline; predates MongoDB. |
| **Used for** | Deprecated. Main pipeline ingests to and cleans in MongoDB via `cleaning.run_mongodb` and the `cleaning` stage in `ingestion.runner`. |
| **Can delete?** | **Yes.** Deprecated. If you use MongoDB ingest only, delete `data/cleaned`, `data/deduped`, `data/filtered`. Keep `data/raw` only if you still have sources that truly write there — most scrapers now stream directly to MongoDB. |

---

#### Book inventory, author profiles

| | |
|--|--|
| **Path** | `data/book_inventory.jsonl`, `data/author_profiles.jsonl` (legacy) |
| **Why saved** | Historical research outputs. |
| **Used for** | Migration only; the active book inventory and author profiles now live in MongoDB when `database.mongodb_uri` is set. |
| **Local vs MongoDB** | **MongoDB: Implemented.** `BookInventoryManager` and research pipeline read/write `book_inventory` and `author_profiles` collections (see `docs/MONGODB_CORPUS_SCHEMA.md`). |
| **Can delete?** | **After migration.** Once `python -m ingestion.discovery.migrate_book_inventory` has been run and spot-checked, JSONL files can be removed. |

---

### Path to Zero Local Storage (Implemented)

| Step | Status | How |
|------|--------|-----|
| 1 | ✅ Done | Book inventory and author profiles: pass `config` with `database.mongodb_uri` to use MongoDB. Run `python -m ingestion.discovery.migrate_book_inventory` to migrate existing JSONL. |
| 2 | ✅ Done | Catalogs already in MongoDB (`catalogs` collection). archive_org, gomidas use `load_catalog_from_mongodb` / `save_catalog_to_mongodb`. |
| 3 | ✅ Done | Augmentation: set `output_backend: "mongodb"` (or `use_mongodb: true`) in config. Output and checkpoint go to MongoDB. |
| 4 | ✅ Done | Set `paths.delete_after_ingest: true` in config. Wikipedia bz2, mss_nkr files, OCR source files deleted after successful ingest. |
| 5 | ✅ Done | Legacy file-based cleaning requires `--force-legacy`. Default: exit with message to use MongoDB cleaning. |
| 6 | ✅ Done | With above: only `config/` and `data/logs` persist. Logs stay in `paths.log_dir` (default `data/logs`). |

**Config for zero local storage:**

```yaml
database:
  use_mongodb: true
  mongodb_uri: "mongodb://localhost:27017/"
  mongodb_database: "western_armenian_corpus"

paths:
  delete_after_ingest: true   # Delete bz2, PDFs, images after ingest
  log_dir: "data/logs"       # Or external path for logs

augmentation:
  source_backend: "mongodb"
  output_backend: "mongodb"
```

**Remaining local-only cases:** None when using the above config. The only hard requirement is that OCR and Wikipedia extraction need the source file **during** the run; they can be deleted **after** the run.

---

### Summary: What Persists Where

| Data | Local path | MongoDB | Notes |
|------|------------|---------|-------|
| Wikipedia bz2 | `data/raw/wikipedia_*/` | — | Deleted after ingest when `delete_after_ingest: true` |
| mss_nkr PDFs/images | `data/raw/mss_nkr/` | — | Deleted after OCR when `delete_after_ingest: true` |
| archive_org, gomidas catalogs | — | `catalogs` | Scrapers read/write MongoDB |
| OCR source files | `data/raw/` | — | Deleted after OCR when `delete_after_ingest: true` |
| Extracted text | — | `documents` | — |
| Augmented text | — | `augmented_documents` | When `output_backend: "mongodb"` |
| Augmentation checkpoint | — | `augmentation_checkpoint` | When using MongoDB backend |
| Book inventory | — | `book_inventory` | When `database.mongodb_uri` set |
| Author profiles | — | `author_profiles` | When `database.mongodb_uri` set |
| Frequency lists | — | `word_frequencies` | — |
| Legacy cleaning | `data/cleaned`, etc. | — | Requires `--force-legacy`; deprecated |
| Logs | `data/logs` | — | Configurable via `paths.log_dir` |
| Document metrics (per-doc) | — | `metadata.document_metrics` | When `database.compute_metrics_on_ingest: true`; slows ingest |

---

## 2. Data Sources: API Documentation Summary

_Source: merged from `DATA_SOURCES_API_REFERENCE.md`._

### Gallica (BnF) — **Implemented**

**Status:** Implemented in `scraping/gallica.py`. No API key required.

#### API type

- **SRU (Search/Retrieve via URL)** — protocol version 1.2  
- **Endpoint:** `https://gallica.bnf.fr/SRU`  
- **Documentation:** [API Gallica – BnF](https://api.bnf.fr/fr/api-gallica-de-recherche), [Protocole SRU](https://www.bnf.fr/fr/protocole-sru-formuler-une-recherche)

#### Parameters

| Parameter         | Required | Description |
|------------------|----------|-------------|
| `version`        | Yes      | `1.2` |
| `operation`      | Yes      | `searchRetrieve` |
| `query`          | Yes      | CQL expression (e.g. `(dc.language any "arm") and (dc.type any "monographie")`) |
| `maximumRecords` | No       | 0–50, default 15 |
| `startRecord`    | No       | Pagination start (1-based) |
| `collapsing`     | No       | Aggregate multi-volume (default `true`) |

#### Query language (CQL)

- **Relations:** `all` (all words), `any` (any word), `adj` (exact phrase)
- **Fields:** `dc.language`, `dc.type`, `dc.subject`, `metadata`, etc.
- **BnF language code for Armenian:** `arm` (in `dc.language`)

#### Response

- XML with Dublin Core / SRU elements; `srw:numberOfRecords` for total; each `record` contains `recordData` with `title`, `identifier` (ARK), `creator`, `date`.

#### Full-text

- OCR text: `https://gallica.bnf.fr/ark:/12148/{ark}.texte` (HTML or plain; strip tags if needed).

#### Config

- `config["scraping"]["gallica"]["queries"]` — list of CQL strings  
- `config["scraping"]["gallica"]["max_results"]` — max items per query (default 200)

---

### DPLA (Digital Public Library of America) — **Implemented**

**Status:** Implemented in `scraping/dpla.py`. **API key required.**

#### API type

- **REST JSON API** — v2  
- **Base URL:** `https://api.dp.la/v2`  
- **Documentation:** [DPLA Developers – Requests](https://pro.dp.la/developers/requests), [Technical Documentation](https://pro.dp.la/developers/technical-documentation)

#### Authentication

- **API key:** Required on every request.  
- **Request a key:** `POST https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com`  
- **Usage:** `?api_key=YOUR_32_CHAR_KEY` or set `config["scraping"]["dpla"]["api_key"]` or env `DPLA_API_KEY`.  
- See `docs/development/requests_guides/DPLA_API_KEY.md` and `docs/development/requests_guides/request_dpla_api_key.ps1` / `request_dpla_api_key.sh`.

#### Items resource

- **URL:** `https://api.dp.la/v2/items`  
- **Parameters:** `page`, `page_size` (max 500), `sourceResource.language.name`, `sourceResource.type`, `q` (full-text search).

#### Response structure

- `docs` — array of items; each has `id`, `sourceResource` (title, description, language, type, format, creator), `isShownAt`, `object`, `dataProvider`.

#### Config

- `config["scraping"]["dpla"]["api_key"]` or `DPLA_API_KEY`

---

### Gomidas Institute — **Implemented**

**Status:** Implemented in `scraping/gomidas.py`. No API; HTML scraping.

#### Access type

- **Website scraping** — no public REST API.  
- **Resources page:** `https://www.gomidas.org/resources.html`  
- **Discovery:** Parse HTML, collect links that match Armenian/newspaper/PDF keywords; follow links to PDFs.

#### Implementation notes

- Catalog built by scraping `resources.html` with BeautifulSoup; PDFs downloaded and run through `ocr/pipeline.py` for text; text ingested to MongoDB.  
- **Rate limiting:** 2 s delay between requests (`_REQUEST_DELAY`).  
- **Bulk permission:** See `docs/GOMIDAS_BULK_PERMISSION.md` if you need formal bulk access.

#### Config

- No API key. Enable via `config["scraping"]["gomidas"]["enabled"]` if present in runner.

---

### Mechitarist Library (San Lazzaro, Venice) — **Not started (stub ready)**

**Status:** Stub in `scraping/mechitarist.py`. No public API; partnership/permission required.

#### Access type

- **Online catalog:** https://catalog.mechitar.org/ (Calfa partnership; searchable manuscript database).  
- **No public REST API** — the catalog is a web application, not an open API.  
- **Library contact:** library@mechitar.org; catalog site: https://www.orlazaroarmeno.it/

#### What exists

- ~1,500+ Armenian printed works (17th–20th c.); manuscript catalog with 2,000+ records (catalog.mechitar.org).  
- Permission template: `docs/MECHITARIST_PERMISSION_REQUEST.md`.

#### Stub implementation

- `scraping/mechitarist.py` provides `run(config)` and a CLI. When no catalog source is configured, it logs that Mechitarist requires permission/export and exits.  
- **When you have access:** Set `config["scraping"]["mechitarist"]["catalog_path"]` to a path to a bulk export (e.g. JSON/CSV), or `config["scraping"]["mechitarist"]["api_base"]` and `api_key` if they provide an API later. The stub is structured so you can plug in a catalog loader and ingest loop.

#### Config (for when access is granted)

- `config["scraping"]["mechitarist"]["catalog_path"]` — path to bulk export file (JSON/JSONL/CSV)  
- `config["scraping"]["mechitarist"]["api_base"]` — optional future API base URL  
- `config["scraping"]["mechitarist"]["api_key"]` — optional future API key  

---

### AGBU Nubar Library (Paris) — **Not started (stub ready)**

**Status:** Stub in `scraping/agbu.py`. No public API; partnership/on-site access.

#### Access type

- **Website:** https://bnulibrary.org — digitized collections, periodicals, archives.  
- **No public REST or bulk-download API** — access is by appointment and partnership.  
- **Contact:** Via site contact form or AGBU (https://agbu.org) for partnership inquiries.

#### What exists

- 43,000+ printed books, 800,000+ archival documents, 1,400 periodicals; Western Armenian diaspora focus.  
- Partnership model (e.g. Calfa): library supplies images/metadata; partner supplies OCR/corpus building.  
- See `docs/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md`.

#### Stub implementation

- `scraping/agbu.py` provides `run(config)` and a CLI. When no data source is configured, it logs that AGBU requires partnership and exits.  
- **When you have access:** Set `config["scraping"]["agbu"]["catalog_path"]` or `export_path` to a bulk export, or `api_base` + `api_key` if they provide an API. The stub is ready for a catalog loader and ingest loop.

#### Config (for when partnership yields data)

- `config["scraping"]["agbu"]["catalog_path"]` or `export_path` — path to bulk export  
- `config["scraping"]["agbu"]["api_base"]` — optional future API base URL  
- `config["scraping"]["agbu"]["api_key"]` — optional future API key  

---

### API & Access Summary

| Source      | API / access           | Key required | Implemented | Notes                          |
|------------|------------------------|--------------|-------------|--------------------------------|
| Gallica    | SRU (no key)           | No           | Yes         | CQL queries, ARK `.texte`      |
| DPLA       | REST v2                | Yes          | Yes         | Request key via POST           |
| Gomidas    | HTML scraping          | No           | Yes         | PDF + OCR                      |
| Mechitarist| None (catalog only)    | N/A          | Stub        | Permission/export needed       |
| AGBU       | None (partnership)     | N/A          | Stub        | Partnership/export needed      |

**Other corpus sources (implemented in this project):** Library of Congress (LOC), HathiTrust, Internet Archive (archive_org), Wikipedia WA/EA, Wikisource, newspaper, ea_news, rss_news, culturax, english_sources, nayiri, gomidas, ocr_ingest, mss_nkr — all wired in `ingestion.runner`. Catalogs and documents are stored in MongoDB. See `docs/SCRAPING_FOLDER_ANALYSIS.md` for per-module status.

---

## 3. Western Armenian Data Sources Expansion

_Source: merged from `DATA_SOURCES_EXPANSION.md`._

### Overview

Research and implementation of additional data sources to expand the Western Armenian training corpus beyond the current ~44M tokens from Internet Archive.

**Date**: March 5, 2026 (updated March 8, 2026; research update March 10, 2026)  
**Goal**: Add 115-255M new tokens from non-public repositories  
**Status**: Implementation complete for LOC, Gallica, Gomidas; HathiTrust blocked (Hathifiles workaround available)

---

### Implementation Status (vs. Doc)

| Source | Doc Status | Actual Status | Notes |
|--------|------------|---------------|-------|
| Internet Archive | ✅ Active | ✅ Implemented | `scraping/archive_org.py`, 39 queries, MongoDB-only |
| Wikipedia (hyw) | ✅ Active | ✅ Implemented | `scraping/wikipedia_wa.py` |
| CulturaX | ⚠️ Gated | ✅ Implemented | `scraping/culturax.py`, HuggingFace gated |
| Newspapers | ✅ Active | ✅ Implemented | `scraping/newspaper.py` (Aztag, Horizon) |
| HathiTrust | ⚠️ 403 blocked | ✅ Implemented | `scraping/hathitrust.py`, blocked on search |
| Library of Congress | 🔄 Partially | ✅ Implemented | `scraping/loc.py`, 1,220 cataloged, slow API |
| Gallica (BNF) | ⏳ Not started | ✅ Implemented | `scraping/gallica.py`, SRU API |
| Mechitarist (Venice) | ⏳ Not started | ❌ Not implemented | Permission template in docs/ |
| Gomidas Newspapers | ⏳ Not started | ✅ Implemented | `scraping/gomidas.py`, PDF→OCR |
| AGBU Nubarian | ⏳ Not started | ❌ Not implemented | Partnership required |
| Wikisource | — | ✅ Implemented | `scraping/wikisource.py` |
| EA News | — | ✅ Implemented | `scraping/ea_news.py` |
| RSS News | — | ✅ Implemented | `scraping/rss_news.py` |
| English Sources | — | ✅ Implemented | `scraping/english_sources.py` |
| Nayiri | — | ✅ Implemented | `scraping/nayiri.py` |
| mss_nkr | — | ✅ Implemented | `scraping/mss_nkr.py` |

---

### Current Data Sources

| Source | Status | Tokens | Items | Location |
|--------|--------|--------|-------|----------|
| Internet Archive | ✅ Active | 44M | Various | `data/raw/archive_org/` |
| Wikipedia (hyw) | ✅ Active | ~2M | Articles | `data/raw/wikipedia/` |
| CulturaX | ⚠️ Gated | 2.96M docs | Corpus | Hugging Face dataset |
| Newspapers | ✅ Active | Small | Aztag, Horizon | `data/raw/newspapers/` |

**Total Current**: ~46-48M tokens

---

### New Sources Research Summary

#### Tier 1 (High Priority - Free APIs)

##### 1. HathiTrust Digital Library

- **Estimated items**: 200-500 Armenian books
- **API access**: Requires permission/bulk dataset request
- **Implementation**: ✅ `scraping/hathitrust.py` (356 lines)
- **Status**: ⚠️ Web scraping blocked (403 Forbidden)
- **Catalog-building options**:
  - **Bibliographic API** is *not* a search API — it returns metadata for *given* IDs (oclc, isbn, htid, lccn). You must supply HTIDs first.
  - **Hathifiles**: Tab-delimited metadata files with a `language` field. Download from [Hathifiles](https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources/hathifiles/), filter `language=arm` for Armenian. Use Bibliographic API to enrich metadata after obtaining HTIDs.
  - **OAI-PMH**: Harvest metadata from https://oai.hathitrust.org/
- **Hathifiles catalog build**: Set `hathifile_path` in config to a downloaded Hathifile; `build_catalog_from_hathifile()` filters `language=arm`, optionally enriches via Bibliographic API.
- **Next steps**:
  - Request research dataset: `docs/HATHITRUST_RESEARCH_DATASET_REQUEST.md`
  - Or download Hathifiles, set `scraping.hathitrust.hathifile_path`, run pipeline
- **Config**: Added to `config/settings.yaml` (queries, max_results: 250)

##### 2. Library of Congress

- **Estimated items**: 1,000+ Armenian manuscripts, books, periodicals
- **API access**: ✅ Free public API (no key required)
- **Implementation**: ✅ `scraping/loc.py` (600+ lines)
- **Status**: 🔄 Partially working — catalog created with 1,220+ items
- **Search queries** (configurable in `config/settings.yaml`): `"armenian"`, `"armenia"`, `"western armenian"`, `"Հայ"`. All search results are kept (no post-filter) to capture any Armenian-related text.
- **Malformed item IDs**: LOC search returns items whose `id` field can be a full URL (e.g. `https://lccn.loc.gov/12345` or `https://www.loc.gov/item/cgi-bin/...`). The code extracts the ID via `item["id"].split("/")[-2]`, which sometimes yields URL fragments like `"lccn.loc.gov"`, `"cgi-bin"`, `"loc.gov"` instead of valid LCCNs. Valid LCCNs look like `2021668001` or `sn86080123`. Malformed IDs cause 404s when requesting `https://www.loc.gov/item/{item_id}/`. Use `python -m ingestion.acquisition.loc catalog --clean` to filter them from existing catalogs; `_is_valid_loc_id()` filters them during search.
- **503/404 diagnostics**: Failed item IDs are logged to `data/logs/loc_api_errors.jsonl` (JSONL: `item_id`, `status`, `message`). 404 = item not found (malformed ID, moved, or restricted). 503 = server overload — retry with backoff.
- **Full catalog**: `python -m ingestion.acquisition.loc catalog --full` — broader queries, higher limits, saves to JSON + MongoDB.
- **Issues**:
  - Very slow API responses (timeouts common)
  - Text extraction from resources still needs validation
- **Catalog**: `data/raw/loc/loc_catalog.json` (1.49 MB, 1,220 items)
- **Config**: Added to `config/settings.yaml` (queries, max_results: 300)
- **Improvements made**:
  - Retry logic with exponential backoff (3 attempts)
  - Reduced timeout (30s → 15s)
  - Malformed ID filtering (`_is_valid_loc_id`, `catalog --clean`)
  - Armenian keyword post-filter removed — all search results kept for maximum coverage
  - Type checking for list/dict variations in API responses

##### 3. French National Library (Gallica)

- **Estimated items**: 50-200 digitized Armenian works
- **API access**: Free via https://gallica.bnf.fr/ SRU API
- **Implementation**: ✅ `scraping/gallica.py` — SRU search, catalog + download
- **Status**: Implemented — run `python -m ingestion.acquisition.gallica run`

---

#### Tier 2 (Permission Required)

##### 4. Mechitarist Congregation (Venice)

- **Estimated items**: 1,500+ printed works (17th-20th century)
- **Access**: Requires permission request
- **Catalog**: https://www.orlazaroarmeno.it/
- **Implementation**: ⏳ Not started

##### 5. Gomidas Institute Newspapers

- **Estimated items**: 5,000+ newspaper pages
- **Access**: Partially online at https://www.gomidas.org/resources.html
- **Implementation**: ✅ `scraping/gomidas.py` — PDF→OCR pipeline
- **Status**: Implemented — run `python -m ingestion.acquisition.gomidas run`
- **Bulk permission**: Ready-to-send draft in `docs/development/requests_guides/GOMIDAS_BULK_PERMISSION.md`

##### 6. AGBU Nubarian Library

- **Estimated items**: 3,000+ modern works; 1,400 periodicals (Ottoman Armenian press); 43,000+ books
- **Access**: Partnership/membership required
- **Implementation**: ⏳ Not started
- **Draft email**: `docs/development/requests_guides/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md` (includes ready-to-send partnership request)

---

### Implementation Details

#### Scraper Architecture

All scrapers follow the standardized pattern from `archive_org.py`:

1. **Catalog-based tracking**: JSON file with item metadata and download status
2. **Resume capability**: Skip already-downloaded items
3. **WA filtering**: Optional application of Western Armenian classifier
4. **Rate limiting**: Configurable delays (`_REQUEST_DELAY`)
5. **Error handling**: Retry logic, exponential backoff, detailed logging

#### Configuration Structure

```yaml
scraping:
  <source_name>:
    queries:
      - "search term 1"
      - "search term 2"
    max_results: 250
    apply_wa_filter: true
```

#### HathiTrust Scraper

**File**: `scraping/hathitrust.py` (356 lines)

**APIs Used**:

- Catalog search (SOLR-based, requires HTML parsing)
- Volume metadata: `https://catalog.hathitrust.org/api/volumes/brief/json/{htid}`
- Page-level text: `https://babel.hathitrust.org/cgi/pt` (Data API)

**Features**:

- Page-by-page download with consecutive failure detection (stops after 5 failures)
- Volume combination into single text file
- Catalog file: `hathitrust_catalog.json`
- Includes warning about bulk dataset request for large-scale use

**Current Issue**: 403 Forbidden on all search queries (web scraping blocked)

**Workaround**: Request bulk research dataset from HathiTrust

#### Library of Congress Scraper

**File**: `scraping/loc.py` (600+ lines)

**APIs Used**:

- JSON search: `https://www.loc.gov/search/` with `fo=json`
- Item metadata: `https://www.loc.gov/item/{lccn}/?fo=json`

**Features**:

- Search queries return all results (no post-filter); full catalog via `catalog --full`
- Text extraction from multiple formats (text/plain, OCR URLs)
- Catalog file: `loc_catalog.json` (1,220 items cataloged)
- Metadata inclusion (title, date, LOC ID) in output files
- Retry logic with exponential backoff (3 attempts, 2-4-8s delays)
- Reduced timeout (15s) to handle slow API

**Current Issues**:

- API very slow with frequent timeouts
- 503/404 errors on some item metadata
- Downloads: 0/1,220 completed (40 attempts before interruption)

**Success Metrics**:

- ✅ Search phase: 1,220 Armenian items cataloged
- ⚠️ Download phase: Slow and error-prone, needs long-running process

---

### Next Steps

#### Immediate (This Week)

1. **HathiTrust**: Submit research dataset request (template: `docs/HATHITRUST_RESEARCH_DATASET_REQUEST.md`) or build catalog from Hathifiles (`language=arm`)
2. **LOC**: Run scraper in background: `python -m ingestion.acquisition.loc run --background`
3. **Gallica**: ✅ Implemented — `python -m ingestion.acquisition.gallica run`
4. **Gomidas**: ✅ Implemented — `python -m ingestion.acquisition.gomidas run`

#### Short-term (2 Weeks)

5. **Mechitarist**: Send permission request (template: `docs/MECHITARIST_PERMISSION_REQUEST.md`)
6. **LOC cleanup**: Run `python -m ingestion.acquisition.loc catalog --clean` to filter malformed IDs from existing catalogs

#### Medium-term (1 Month)

7. **AGBU**: Explore partnership options for library access
8. **Validation**: Apply WA filter to all downloaded content
9. **Integration**: Add new data to training pipeline

---

### Technical Notes

#### No API Keys Required

Both HathiTrust and Library of Congress provide free public APIs for public domain content. No authentication or API keys are needed.

#### Rate Limiting

- **LOC**: 1.5s delay between requests (slow API, be conservative)
- **HathiTrust**: 1.0s delay (if using Data API after bulk dataset approval)

#### Error Handling Improvements

All scrapers now include:

- Retry logic with exponential backoff (3 attempts)
- Reduced timeouts (15–20s instead of 30–60s)
- Type checking for API response variations
- Graceful handling of malformed data

#### Estimated Timeline

- **HathiTrust**: 2–4 weeks (dataset request approval time)
- **LOC**: 1–3 days (slow downloads; 1,220 items × ~3–5s/item)
- **Gallica**: 1–2 days (implementation + testing)
- **Total new tokens**: 115–255M (2.5–5.3× current corpus size)

---

### Storage: MongoDB Only (No JSON/txt Persistence)

**All data is stored in MongoDB only.** No catalog JSON files, no `.txt` downloads. Only logging files (e.g. `data/logs/loc_api_errors.jsonl`) are written for error triage.

**MongoDB collections**:

- `documents` — corpus text (source, title, text, metadata)
- `catalogs` — `{source, item_id, title, url, downloaded, ...}` for LOC, HathiTrust, Gallica, Gomidas, archive_org

---

### Implementation Plan (Priority Order)

#### Phase 1: Free APIs (1–2 weeks)

1. **Gallica (BNF)** — ✅ Implemented. Run `python -m ingestion.acquisition.gallica run`.
2. **LOC cleanup** — Run `python -m ingestion.acquisition.loc catalog --clean`; add retry/backoff for 503s; run overnight with `run --background`.
3. **HathiTrust** — Submit research dataset request; or download Hathifiles, filter `language=arm`, build catalog (Bibliographic API enriches metadata for given HTIDs, it does not search).

#### Phase 2: Permission-Based (2–4 weeks)

4. **Gomidas** — ✅ Implemented. Run `python -m ingestion.acquisition.gomidas run`; request permission for bulk access.
5. **Mechitarist** — Send permission request (template: `docs/MECHITARIST_PERMISSION_REQUEST.md`); if granted, implement catalog + PDF/image download.
6. **AGBU Nubarian** — Explore partnership; catalog may be searchable via WorldCat.

#### Phase 3: OCR-First Sources (ongoing)

7. **PDF/Image ingest pipeline** — Add `scraping/ocr_ingest.py` to accept local PDF/image dirs, run `ocr/pipeline.py`, insert to MongoDB with dialect tagging.
8. **University repositories** — UCLA, Columbia, Harvard have Armenian holdings; many are PDF-only.
9. **ArchiveGrid / DPLA** — Aggregate APIs for Armenian materials across US institutions.

---

### Additional Source Brainstorm (Implementation Plan)

#### Digital Libraries (API / Bulk) — Planned

- **Gallica (BNF)** — ✅ Implemented
- **Europeana** — EU aggregator, Armenian filter, mixed formats
- **Digital Public Library of America (DPLA)** — US aggregator, `api.dp.la/v2/items`, API key required
- **WorldCat** — `worldcat_searcher.py` exists; wire to drive LOC/IA/Hathi lookups + dedup
- **Österreichische Nationalbibliothek** — Austrian National Library, Armenian manuscripts
- **Bayerische Staatsbibliothek** — Munich, Oriental collections
- **Leiden University Library** — Armenian studies collection

#### University / Research — Planned

- **UCLA Armenian Studies** — PDFs, dissertations, periodicals
- **Columbia Armenian Studies** — Rare books, some digitized
- **Harvard Widener** — Armenian holdings, HathiTrust overlap (add dedup)
- **University of Michigan Armenian Studies** — Program + possible digitized holdings
- **NAASR (National Association for Armenian Studies and Research)** — Publications, some online
- **Armenian studies programs worldwide** — Survey for data sources (e.g., Sorbonne, Oxford, etc.)

#### Newspapers / Periodicals (Scanned)

- **Gomidas Institute** — ✅ Implemented; bulk permission: `docs/development/requests_guides/GOMIDAS_BULK_PERMISSION.md`
- **British Library EAP** — Ottoman-era Armenian newspapers (EAP613, EAP180); IIIF access; see “Research: Additional Sources” below
- **Armenian General Benevolent Union (AGBU) archives** — Periodicals
- **Zohrab Center (NYC)** — Armenian ecclesiastical texts, some digitized
- **Calouste Gulbenkian Foundation** — Lisbon, Armenian collection

#### Manuscript / Image-Only — Planned

- **Matenadaran (Yerevan)** — Manuscripts, some digitized as images
- **Armenian Museum of America** — Scanned documents
- **Mekhitarist Vienna branch** — Additional to Venice
- **St. James Armenian Monastery (Jerusalem)** — Manuscripts

#### OCR Pipeline Integration

For any source that provides only PDFs or images:

1. Download to `data/raw/<source>/`
2. Run `ocr/pipeline.py` with `hye` or `hye+eng` per document
3. Ingest output via `scraping/ocr_ingest.py` → MongoDB with `metadata.language_code` (hyw/hye/hy)

---

### Research: Additional Sources (March 2026)

Answers to common expansion questions.

#### UK Centre for Western Armenian Studies (CFWAS)

- **Website**: https://cfwas.org.uk/
- **Archives / data**: The **Memory Documentation Project** (https://cfwas.org.uk/mdp/) collects audio-visual and written recordings of interviews (first Diaspora-born generation post-Genocide). Materials are intended to be “made free and available to the public” with consent; transcriptions may be translated into Western Armenian and English.
- **Format**: Interviews, transcriptions, scanned letters/photographs. No public API or bulk download documented.
- **For corpus use**: Contact CFWAS directly to ask about research access to transcripts or text exports. Not suitable for scraping without permission.

#### Ottoman-Era Armenian Newspapers

Several digitized archives exist:

- **British Library — Endangered Archives Programme (EAP)**  
  - **EAP613**: “Digital preservation and cataloguing of early printed Armenian maps, periodicals and newspapers” — 113 digitized newspapers among 547 records (Armenian script).  
  - **EAP180**: Endangered Armenian rare books and periodicals, including the daily *Nor dar* (1884–1908); 878 folders, 2,530 images.  
  - **Access**: https://eap.bl.uk/ — search/browse; images use **IIIF** (add `/manifest` to file URLs). No public API; reuse for research may require permission from original custodians. Third-party tools (e.g. IIIF download tools, GitHub “eap-books-rescue”) exist for image download.
- **Clark University — Guerguerian Archive**: Armenian-language sections of *Takvim-i Vekayi* (official Ottoman gazette), including 1919 Military Tribunal minutes; indexed digitized materials.
- **AGBU Nubarian Library**: 1,400 periodical collections (Ottoman Armenian press) — see partnership request above.
- **Gomidas Institute**: 5,000+ digitized newspaper pages — see bulk permission draft above.

#### Official Armenian Government Resources and National Libraries

- **National Library of Armenia (NLA)**: https://nla.am/en_US  
  - **Holdings**: 6M+ digitized pages (books and periodicals); 93,691+ PDFs with OCR (as of 2023). Union Catalog: https://armunicat.nla.am ; DSpace repository: dspace.nla.am.  
  - **Terms**: Copying/scanning for personal, educational, or research use permitted under RA copyright law (limits e.g. one article per issue, one chapter or ≤10% of a book).  
  - **Scraping / API**: No documented public API for programmatic access. Do **not** scrape without permission. Contact NLA for terms and possible research or bulk access (+37460 623513).
- **Other official/library sources**: Any government or national library site should be contacted for terms before scraping; many collections are Eastern Armenian–heavy and may need dialect filtering.

#### Other Libraries and Archives with Armenian Text Data

- **Nayiri / COWA (Corpus of Western Armenian)**: https://www.nayiri.com/text-corpus — Western Armenian corpus (beta), linguistic search; check terms for bulk or API.
- **EANC (Eastern Armenian National Corpus)**: http://eanc.net/en/armenian_texts_online/ — Eastern Armenian; useful for comparison or dialect filtering, not primary WA source.
- **British Library EAP**: See “Ottoman-Era Armenian Newspapers” above.
- **Matenadaran (Yerevan)**: Manuscripts; some digitized as images; permission/partnership typically required.
- **Zohrab Center (NYC)**: Ecclesiastical texts, some digitized.
- **Calouste Gulbenkian Foundation (Lisbon)**: Armenian collection.
- **University / NAASR / NAASR-style institutions**: Already listed in “Additional Source Brainstorm” (UCLA, Columbia, Harvard, NAASR, etc.).

---

### References

1. HathiTrust Research Dataset Request: https://www.hathitrust.org/help_digital_library
2. Library of Congress JSON API: https://www.loc.gov/apis/json-and-yaml/
3. Gallica API Documentation: https://gallica.bnf.fr/services/engine/search/sru
4. Mechitarist Library Catalog: https://www.orlazaroarmeno.it/
5. Gomidas Institute Resources: https://www.gomidas.org/resources.html
6. Europeana API: https://pro.europeana.eu/page/apis
7. DPLA API: https://pro.dp.la/developers/api
8. ArchiveGrid: https://researchworks.oclc.org/archivegrid/
9. British Library EAP: https://eap.bl.uk/ (Armenian: EAP613, EAP180)
10. UK Centre for Western Armenian Studies: https://cfwas.org.uk/ (Memory Documentation Project: https://cfwas.org.uk/mdp/)
11. National Library of Armenia: https://nla.am/en_US (Union Catalog: https://armunicat.nla.am ; DSpace: dspace.nla.am)
12. Nayiri / COWA: https://www.nayiri.com/text-corpus
13. EANC: http://eanc.net/en/armenian_texts_online/

---

### Contact Information

For permissions and dataset requests:

- **HathiTrust**: feedback@issues.hathitrust.org
- **Mechitarist Library**: library@mechitar.org (Venice)
- **AGBU Nubarian**: contact via https://www.agbu.org/ or https://bnulibrary.org
- **Gomidas Institute**: info@gomidas.org (verify on site)
- **UK Centre for Western Armenian Studies**: via https://cfwas.org.uk/
- **National Library of Armenia**: +37460 623513; https://nla.am/en_US (for programmatic/bulk access)

