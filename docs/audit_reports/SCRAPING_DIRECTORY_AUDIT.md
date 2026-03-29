# Ingestion Directory — Audit and Organization (Implemented)

**Date:** 2026-03-12  
**Scope:** Former `scraping/` directory; now **`ingestion/`** with Option B subpackages.  
**Status:** Renamed to **ingestion**; reorganized by function (Option B); `scraping/` has been removed; use `ingestion` only (`python -m scraping.runner` → `ingestion.runner`).

---

## 1. Executive Summary

The `scraping/` directory is a **single flat package** that mixes several distinct responsibilities:

- **Acquisition** — Fetch from external APIs, dumps, or files → MongoDB
- **Extraction** — Read from another store (e.g. SQLite) → MongoDB
- **Enrichment** — Add or backfill metadata/views on existing MongoDB documents
- **Aggregation / analytics** — Build derived collections (word frequencies, summaries, facets)
- **Validation / integrity** — Check corpus alignment, export fingerprints
- **Discovery** — WorldCat search (catalog discovery, not bulk load)
- **Shared utilities** — MongoDB helpers, metadata schema, mappers, registry
- **Orchestration** — Runner that sequences all stages

The name **“scraping”** is misleading: only a subset of modules perform web scraping; the rest do ingestion from APIs/dumps, extraction from SQLite, enrichment, and document-store analytics. This audit recommends **organization by function** (subpackages or clear naming) and **alternative top-level naming** that reflects “data acquisition + extraction + enrichment + load into document store” without implying relational ETL.

---

## 2. Inventory by Function

### 2.1 Acquisition (external source → MongoDB)

| Module | Source type | Entry | Notes |
|--------|-------------|-------|--------|
| `wiki` | Wikimedia dumps + API | `run_wikipedia`, `run_wikisource` | Single module, two stages |
| `archive_org` | Internet Archive API | `run` | Catalog-based |
| `hathitrust` | HathiTrust API | `run` | Catalog-based |
| `gallica` | BnF Gallica API | `run` | Catalog-based |
| `loc` | Library of Congress API | `run` | Catalog-based |
| `dpla` | DPLA API (key required) | `run` | |
| `news` | Newspapers (Selenium) + EA agencies + RSS | `run` | Unified news stage |
| `culturax` | HuggingFace dataset | `run` | |
| `english_sources` | Dynamic discovery | `run` | |
| `nayiri` | Nayiri.com dictionary | `run` | |
| `gomidas` | Gomidas Institute (PDF/OCR) | `run` | |
| `mechitarist` | Mechitarist (stub) | `run` | |
| `agbu` | AGBU (stub) | `run` | |
| `ocr_ingest` | Local OCR output / files | `run` | Generic file ingest |
| `mss_nkr` | Matenadaran NKR archive | `run`, `main` | |

**Count:** 15 acquisition modules (wiki counts as 2 logical sources).

### 2.2 Discovery (catalog search, not bulk load)

| Module | Role | Entry |
|--------|------|--------|
| `worldcat_searcher` | WorldCat catalog search | `main` |

### 2.3 Extraction (other store → MongoDB)

| Module | Source | Entry |
|--------|--------|--------|
| `import_anki_to_mongodb` | AnkiConnect → MongoDB | `main` |

### 2.4 Enrichment (MongoDB → MongoDB, add/backfill fields)

| Module | Role | Entry |
|--------|------|--------|
| `metadata_tagger` | Source → dialect/region/source_type backfill | `run` |
| `materialize_dialect_views` | Set `dialect_view` for filtered queries | `run` |

### 2.5 Aggregation / analytics (MongoDB → derived collections)

| Module | Output | Entry |
|--------|--------|--------|
| `frequency_aggregator` | `word_frequencies` collection | `run` |
| `word_frequency_facets` | `word_frequencies_facets` (author/source/dialect/year/region) | CLI `aggregate` / `query` |
| `summarize_unified_documents` | Metadata collection (summary stats) | `run` |

### 2.6 Validation / integrity (MongoDB read → report or export)

| Module | Role | Entry |
|--------|------|--------|
| `validate_contract_alignment` | Corpus integrity checks | `run`, `main` |
| `export_corpus_overlap_fingerprints` | Near-duplicate detection, fingerprint export | `run`, `main` |

### 2.7 Shared / core (no pipeline stage)

| Module | Role |
|--------|------|
| `_helpers` | MongoDB client, WA classifier, wikitext, newspaper splitter, catalog I/O, logging |
| `metadata` | `TextMetadata`, `Dialect`, `Region`, `SourceType`, etc. |
| `data_sources` | `get_news_documents`, `get_news_sources` (stub interfaces for downstream) |
| `mappers` | `anki_card_row_to_lexicon_entry`, `sentence_row_to_document_record` |
| `registry` | `ExtractionRegistry`, tool specs, pipeline order |

### 2.8 Orchestration

| Module | Role |
|--------|------|
| `runner` | `run`, `status`, `list`, `dashboard`; `_build_stages()` registers all stages |

---

## 3. Gaps and Inconsistencies

1. **`word_frequency_facets` not in runner**  
   Documented in STRUCTURE.md and MONGODB_CORPUS_SCHEMA.md and has its own CLI (`python -m scraping.word_frequency_facets aggregate`), but it is **not** listed in `runner._build_stages()`. Either add it as a stage (e.g. after `frequency_aggregator`) or document that it is intentionally run separately.

   **How it differs from `frequency_aggregator`:**  
   - **frequency_aggregator**: Reads document **text** from MongoDB, tokenizes Armenian words, builds a **single global** word-frequency list with per-source counts and source weights, stores in `word_frequencies` (one row per word: `total_count`, `source_counts`, `in_nayiri`, `rank`). Used for vocabulary and weighted frequency.  
   - **word_frequency_facets**: Reads **metadata.document_metrics.word_counts** (precomputed at ingest) and aggregates by **facets** (author, source, dialect, year, region). Stores in `word_frequencies_facets` as `(facet, facet_value, word, count)`. Used for queries like “how often does word X appear by author/source/dialect/year/region”. So it is **multi-dimensional** and depends on `document_metrics` being populated at ingest. They are complementary; both are now runnable as pipeline stages.

2. **Cleaning stage lives outside scraping**  
   `cleaning.run_mongodb` is referenced from the runner as a stage. Conceptually it is “post-acquisition normalization” and fits the same pipeline; the current split (cleaning in `cleaning/`, rest in `scraping/`) is acceptable but could be reflected in naming (e.g. “corpus pipeline” that includes both).

3. **STRUCTURE.md out of date**  
   It lists `wikipedia_wa.py`, `wikipedia_ea.py`, `wikisource.py`, `newspaper.py`, `ea_news.py`, `rss_news.py`. Actual layout uses `wiki.py` (Wikipedia + Wikisource) and `news.py` (unified). Update STRUCTURE.md to match.

4. **Add-new-scraper skill suggests subpackages that don’t exist**  
   The skill mentions `wikimedia/`, `digital_libraries/`, `news/`, `datasets/`, `reference/`. The codebase is flat. Either implement subpackages (see below) or update the skill to say “flat under `scraping/`”.

5. **Entry-point inconsistency**  
   Most stages use `run(config)`; a few use `main()` only (`import_anki_to_mongodb`, `worldcat_searcher`, `export_corpus_overlap_fingerprints`, `validate_contract_alignment`). Runner handles both; for consistency and testability, prefer `run(config)` where applicable and have `main()` call it.

---

## 4. Naming Convention Recommendations

You asked for a standard naming convention other than “scraper,” given that the directory does **data extraction, enrichment, and loading** but **no transformation into a relational database** — everything targets a document/NoSQL (MongoDB, JSON-style) store.

### Why “scraper” is narrow

- “Scraper” usually implies **web scraping** (HTML, APIs for web content).  
- Here you also have: dump ingestion (Wikipedia), dataset load (CulturaX), SQLite extraction (Anki), file/OCR ingest, metadata enrichment, and aggregation. So “scraper” covers only part of the work.

### Why “ETL” is only partly fitting

- **E (Extract):** Yes — from web, APIs, dumps, SQLite, files.  
- **T (Transform):** There is normalization and enrichment (e.g. dialect tagging, metadata backfill), but the target is **not** a relational schema; it’s document-oriented. So “ETL” often implies “transform into tables,” which you don’t do.  
- **L (Load):** Yes — into MongoDB (document store).

So “ETL” can be used if you clarify “load into document store, not relational.” Alternatives that avoid that implication:

### Recommended naming options

| Term | Pros | Cons |
|------|------|------|
| **Ingestion** | Standard in data pipelines; agnostic to source (web, API, file, DB). | Can sound like “only loading”; enrichment is a separate concept. |
| **Acquisition** | Common in NLP/corpus pipelines (“data acquisition”). Fits “get data from many sources.” | Slightly vague. |
| **Corpus pipeline** | Domain-clear: “everything that builds the corpus.” | Long; usually need a short package name. |
| **EL (Extract–Load)** | Accurate: extract from sources, load into store. No “T” to relational. | Less familiar than “ETL”; might need a sentence of explanation. |
| **Load** | Simple. | Doesn’t convey extraction or enrichment. |

**Recommendation:**

- **Package name:** Prefer **`ingestion`** or **`acquisition`** as the top-level directory name if you rename:
  - **`ingestion`** — “All stages that bring data into the corpus (acquire, extract, enrich, load).”
  - **`acquisition`** — “Data acquisition pipeline for the Armenian corpus.”
- **Stage naming (internal):**
  - **Acquisition / ingest** — keep source-based names: `wikipedia`, `archive_org`, `loc`, `news`, `culturax`, etc. No need to suffix “_scraper” or “_ingest” for every one; the runner already groups them.
  - **Extraction** — name by source: `import_anki_to_mongodb` is clear.
  - **Enrichment** — `metadata_tagger`, `materialize_dialect_views` are already clear.
  - **Aggregation** — `frequency_aggregator`, `word_frequency_facets`, `summarize_unified_documents` are clear.
  - **Validation** — `validate_contract_alignment`, `export_corpus_overlap_fingerprints` are clear.

If you keep the directory name **`scraping`** for backward compatibility, at least use **“data acquisition”** or **“corpus ingestion pipeline”** in docs and docstrings so readers understand it’s broader than web scraping.

---

## 5. Organization Improvements (Form and Function)

### Option A: Keep flat, improve docs and runner

- **No structural change.** Keep all modules in `scraping/` (or renamed package) as a single flat list.
- **Do:**
  - Add `word_frequency_facets` to `_build_stages()` if it should run in the main pipeline, or document that it is opt-in/CLI-only.
  - Update `scraping/__init__.py` and STRUCTURE.md to group stages by function (acquisition, extraction, enrichment, aggregation, validation) and list `word_frequency_facets` correctly.
  - Align add-new-scraper skill with “flat layout” and list the logical groups (Wikimedia, digital libraries, news, datasets, reference, extraction, enrichment, aggregation).

**Pros:** No import or path changes; minimal risk.  
**Cons:** Directory still has 30+ files in one flat list; discovery is by doc/convention only.

### Option B: Subpackages by function (recommended if you refactor)

Group by **function** so that “scraping” (or “ingestion”) is an umbrella and subpackages reflect roles:

```
scraping/   (or ingestion/)
├── __init__.py
├── runner.py              # Orchestration; imports from subpackages
├── _shared/                # or _core/
│   ├── __init__.py
│   ├── helpers.py          # was _helpers.py (MongoDB, WA, wikitext, etc.)
│   ├── metadata.py
│   ├── mappers.py
│   ├── data_sources.py
│   └── registry.py
├── acquisition/            # External source → MongoDB
│   ├── __init__.py
│   ├── wiki.py
│   ├── archive_org.py
│   ├── hathitrust.py
│   ├── gallica.py
│   ├── loc.py
│   ├── dpla.py
│   ├── news.py
│   ├── culturax.py
│   ├── english_sources.py
│   ├── nayiri.py
│   ├── gomidas.py
│   ├── mechitarist.py
│   ├── agbu.py
│   ├── ocr_ingest.py
│   └── mss_nkr.py
├── discovery/
│   ├── __init__.py
│   └── worldcat_searcher.py
├── extraction/             # Other store → MongoDB
│   ├── __init__.py
│   └── import_anki_to_mongodb.py
├── enrichment/             # MongoDB → MongoDB (add/backfill)
│   ├── __init__.py
│   ├── metadata_tagger.py
│   └── materialize_dialect_views.py
├── aggregation/            # MongoDB → derived collections
│   ├── __init__.py
│   ├── frequency_aggregator.py
│   ├── word_frequency_facets.py
│   └── summarize_unified_documents.py
└── validation/             # Integrity, fingerprint export
    ├── __init__.py
    ├── validate_contract_alignment.py
    └── export_corpus_overlap_fingerprints.py
```

- **Stage registration:** In `runner._build_stages()`, use module paths like `scraping.acquisition.wiki`, `scraping.enrichment.metadata_tagger`, etc.
- **Imports:** All internal imports must be updated (e.g. `from scraping._helpers` → `from scraping._shared.helpers` or keep a top-level re-export in `scraping/__init__.py` for backward compatibility during migration).
- **External references:** `integrations.database`, `research`, `tests` reference `scraping._helpers` and others; update or add compatibility shims.

**Pros:** Clear separation by function; easier to onboard and to add new stages in the right place.  
**Cons:** Larger refactor; many import paths and runner stage modules to update.

### Option C: Subpackages by source type (alternative)

Group acquisition by **source type** (as in the add-new-scraper skill), and keep enrichment/aggregation/validation as separate groups:

```
scraping/
├── runner.py
├── _shared/   (as in B)
├── wikimedia/       # wiki (Wikipedia + Wikisource)
├── digital_libraries/  # archive_org, hathitrust, gallica, loc, dpla
├── news/             # news (unified)
├── datasets/         # culturax, english_sources
├── reference/        # nayiri, gomidas, mechitarist, agbu, mss_nkr
├── ingest/           # ocr_ingest (generic file ingest)
├── discovery/        # worldcat_searcher
├── extraction/       # import_anki_to_mongodb
├── enrichment/       # metadata_tagger, materialize_dialect_views
├── aggregation/      # frequency_aggregator, word_frequency_facets, summarize_unified_documents
└── validation/       # validate_contract_alignment, export_corpus_overlap_fingerprints
```

**Pros:** Matches “add a new scraper” by source type.  
**Cons:** More top-level packages; “reference” and “datasets” are a bit fuzzy (e.g. culturax is a dataset, nayiri is reference).

### Research directory: place under ingestion? — **Done (2026-03)**

The former **`research/`** directory has been **moved under `ingestion/`**. Processes that mine attributes and add metadata for data enrichment now live as follows:

| Module | New location | Role |
|--------|---------------|------|
| `author_extraction` | `ingestion/discovery/author_extraction.py` | Extract author names from corpus (metadata, book inventory, citations, text) |
| `author_research` | `ingestion/discovery/author_research.py` | Author profile schema and persistence (AuthorProfile, AuthorProfileManager) |
| `biography_enrichment` | `ingestion/enrichment/biography_enrichment.py` | Enrich author profiles (Wikipedia, manual DB: birth/death, bio, works) |
| `book_inventory` | `ingestion/discovery/book_inventory.py` | Track canonical works; WorldCat/LOC/Archive.org; corpus scan for titles |
| `book_inventory_runner` | `ingestion/discovery/book_inventory_runner.py` | CLI for inventory acquisition (can call WorldCat) |
| `coverage_analysis` | `ingestion/aggregation/coverage_analysis.py` | Author/period/genre/work coverage gaps; acquisition checklists |
| `timeline_generation` | `ingestion/aggregation/timeline_generation.py` | Author lifespans, publication timelines, period analysis |
| `research_pipeline` | `ingestion/research_runner.py` | Orchestrates: extraction → biography enrichment → timeline → coverage |
| `pipeline_config` | `ingestion/_shared/research_config.py` | `get_research_config` (exclude_dirs, error_threshold_pct) |
| `worldcat_searcher` | `ingestion/discovery/worldcat_searcher.py` | WorldCat API and fallback; imports `ingestion.discovery.book_inventory` |

**Entry points:** `python -m ingestion.discovery.book_inventory_runner`, `python -m ingestion.research_runner`. Imports use `ingestion.discovery.*`, `ingestion.enrichment.biography_enrichment`, `ingestion.aggregation.coverage_analysis`, `ingestion.aggregation.timeline_generation`, `ingestion._shared.research_config`.

### Augmentation directory: place under ingestion?

The **`augmentation/`** directory implements **synthetic data generation** for the Western Armenian corpus:

| Module | Role |
|--------|------|
| `strategies` | LLM-based (paraphrase, continue, topic_write) and non-LLM text transforms |
| `llm_client` | HTTP client for Ollama/OpenAI |
| `safe_generation` | Rejection sampling so output passes WA validation |
| `batch_worker` | Scan source docs, build task queue, run strategies, checkpoint, write to MongoDB or filesystem |
| `runner` | CLI: estimate, run, status, metrics (separate from scraping runner) |
| `metrics_pipeline` | Compute metrics before/after augmentation; store in MongoDB |
| `baseline_statistics` | Corpus-level baseline (mean, std, percentiles) for metrics |
| `drift_detection` | Anomaly/drift alerts vs baseline |
| `metrics_visualization` | Plot metric distributions |
| `calibrate_distance_weights` / `benchmark_dialect_distance` | Dialect distance tuning and benchmarking |

**Recommendation: no — keep `augmentation/` as a sibling to ingestion**, not under it.

- **Different function:** Ingestion = acquire from external sources + extract from other stores + enrich *metadata* on existing documents. Augmentation = **generate new text** from existing corpus via an LLM (and optionally non-LLM transforms). The former is “bring in and tag data”; the latter is “synthesize new training examples.” Putting LLM-based text generation under ingestion would stretch “ingestion” to mean “anything that adds data to the corpus,” which blurs the line between external acquisition and synthetic generation.
- **Pipeline order:** The flow is **ingest → clean → augment → (train)**. Augmentation consumes the output of ingestion and cleaning (MongoDB or cleaned/filtered files); it is a **downstream** stage, not a sub-step of ingestion. The scraping runner does not register augmentation as a stage; augmentation has its own CLI (`python -m augmentation.runner`). Structurally, augmentation is a sibling pipeline.
- **Coupling:** Augmentation does not depend on scraping. It uses `linguistics.metrics`, `cleaning.language_filter`, and `integrations.database.mongodb_client`. Scraping has one **optional** use of augmentation: `_helpers` can call `augmentation.baseline_statistics.CorpusBaselineComputer` for drift check on ingest. That is a narrow, optional integration (config-driven); it does not justify nesting augmentation under ingestion.
- **Convention:** In ML/data pipelines, “ingestion” or “data acquisition” usually means “get data from the world into the system.” “Data augmentation” is typically a separate stage (often adjacent to training). Keeping `augmentation/` as a top-level package matches that convention and keeps “ingestion” focused on acquisition, extraction, and metadata enrichment.

**Summary:** Keep augmentation as its own package. Treat ingestion as “acquire + extract + enrich metadata”; treat augmentation as “synthesize new WA text from existing corpus.” No structural change needed for augmentation when renaming scraping to ingestion.

### Augmentation: corpus-core vs WesternArmenianLLM?

Augmentation exists to produce **extra training data** for the Western Armenian LLM, so one can ask whether it belongs in **WesternArmenianLLM** (training repo) instead of **armenian-corpus-core**.

**Recommendation: keep augmentation in armenian-corpus-core.**

- **Conceptual split:** One can argue either way: (1) Corpus-core = "build and expand the corpus" (acquisition + enrichment + synthetic expansion); training repo = "consume corpus and train." (2) WA-LLM = "everything from corpus in to model out" (clean, augment, split, train). The current choice is (1): augmentation is **corpus expansion**; the training repo consumes the corpus (filtered, splits, or MongoDB). Keeping augmentation in corpus-core preserves a single place that owns "what is in the corpus."
- **Dependency:** Augmentation depends heavily on **linguistics** (`validate_augmentation_output`, text metrics, dialect purity), **cleaning** (`is_western_armenian`), and **integrations.database** (MongoDB client). Those all live in corpus-core. WesternArmenianLLM already installs `armenian-corpus-core[augmentation]` (see its `requirements.txt`). If we moved the augmentation *code* into WA-LLM, we would still need to import those from corpus-core, so the dependency would remain and we'd split one feature across two repos (runner/strategies in WA-LLM, validation/DB in corpus-core). Keeping augmentation in corpus-core avoids that split.
- **Using augmentation from the training pipeline:** The training repo can **invoke** augmentation without owning its code: e.g. a step in `prepare_training_data` (or a separate CLI) that runs `python -m augmentation.runner run` (from the same environment where corpus-core is installed), then `create_splits` (or a merge step) reads from MongoDB / `data/augmented`. No need to move the code for WA-LLM to "include" augmentation in its workflow.

**Summary:** Keep augmentation in corpus-core. Have the training pipeline call corpus-core's augmentation runner when synthetic data is desired; keep a single codebase for corpus expansion (ingestion + augmentation).

---

## 7. Implemented Changes (2026-03-12)

- **Naming:** Package renamed to **`ingestion`**. Config supports both **`ingestion`** and **`scraping`** keys.
- **Runner and facets:** **`word_frequency_facets`** added as a pipeline stage (after `frequency_aggregator`) with **`run(config)`**.
- **Docs:** **STRUCTURE.md** and **add-new-scraper skill** updated to Option B and ingestion paths.
- **Organization:** **Option B** implemented: `ingestion/_shared`, `acquisition`, `discovery`, `extraction`, `enrichment`, `aggregation`, `validation`. **`scraping/`** kept as compat shim (only `runner.py` delegating to `ingestion.runner`).
- **Entry points:** All stages use **`run(config)`**; **`main()`** calls it. Updated: `import_anki_to_mongodb`, `worldcat_searcher`, `export_corpus_overlap_fingerprints`, `validate_contract_alignment`.

---

## 6. Recommended Next Steps (pre-implementation; see §7 for what was done)

1. **Naming**
   - Decide whether to keep **`scraping`** or rename to **`ingestion`** or **`acquisition`**. If keeping `scraping`, document in `scraping/__init__.py` and AGENTS.md that “scraping” means the full **corpus ingestion pipeline** (acquisition, extraction, enrichment, load into document store).
   - Use **stage names** as-is (wikipedia, archive_org, metadata_tagger, etc.); they already reflect form/function.

2. **Runner and facets**
   - Either add **`word_frequency_facets`** as a runner stage (e.g. after `frequency_aggregator`) or document in runner and STRUCTURE.md that it is a **separate CLI** and not part of the default pipeline.

3. **Docs**
   - Update **STRUCTURE.md** to the current flat file list (wiki.py, news.py, etc.) and add a short “by function” table (acquisition, extraction, enrichment, aggregation, validation).
   - Update **add-new-scraper skill** to match reality: flat layout and logical groups, or describe the chosen subpackage layout if you adopt Option B or C.

4. **Organization**
   - **Short term:** Option A (flat + better docs + runner fix for word_frequency_facets).
   - **Medium term:** If the flat list becomes hard to navigate, move to **Option B** (subpackages by function) and update runner, imports, and tests in one pass.
   - **Research:** **Done.** **`research/`** has been moved under **`ingestion/`** (discovery, enrichment, aggregation, research_runner, _shared/research_config). See "Research directory: place under ingestion?" above for current paths.
   - **Augmentation:** Keep **`augmentation/`** as a **sibling** to ingestion (see "Augmentation directory: place under ingestion?" above). It is synthetic data generation (LLM-based), not acquisition or metadata enrichment; pipeline order is ingest → clean → augment.

5. **Entry points**
   - Prefer **`run(config)`** for all pipeline stages and have **`main()`** call it where it makes sense, so the runner and tests can invoke stages uniformly.

---

## 7. Summary Table: Function vs Current Name

| Function           | Current modules (examples)                    | Suggested umbrella term in docs |
|--------------------|-----------------------------------------------|----------------------------------|
| Acquire from web/API/dump | wiki, archive_org, loc, news, culturax, … | Acquisition / ingest             |
| Extract from other DB     | import_anki_to_mongodb                      | Extraction                       |
| Enrich in place          | metadata_tagger, materialize_dialect_views | Enrichment                       |
| Aggregate / analytics   | frequency_aggregator, word_frequency_facets, summarize_unified_documents | Aggregation                      |
| Validate / export        | validate_contract_alignment, export_corpus_overlap_fingerprints | Validation                       |
| Discovery                | worldcat_searcher, book_inventory, book_inventory_runner, author_research, author_extraction (`ingestion/discovery/`) | Discovery / catalog              |
| Author/book research    | research_runner, biography_enrichment, coverage_analysis, timeline_generation, research_config (`ingestion/`) | Research pipeline                 |
| Shared                  | _helpers, metadata, mappers, registry, data_sources, research_config (`ingestion/_shared/`) | Core / shared                    |

Using **“ingestion”** or **“acquisition”** as the top-level name (or as the documented meaning of “scraping”) aligns the directory name with the full pipeline and avoids implying “only web scraping.” Avoiding “ETL” unless you explicitly mean “extract and load into document store” keeps the naming accurate for a NoSQL/JSON-style target.
