# Western Armenian LLM - Migration Inventory Summary

**Generated:** 2026-03-06  
**Workspace:** C:\Users\litni\WesternArmenianLLM  
**Scope:** Read-only inventory for unified platform extraction

---

## 📊 Summary Counts

### Code Modules
- **Total Python files:** 96
- **Module categories:**
  - Corpus processors: 27
  - Scraping modules: 16
  - Database infrastructure: 15
  - Utilities: 13
  - Research pipeline: 11
  - Training: 5
  - Serving: 4
  - Retrieval (RAG): 4
  - Linguistics: 1

### Data Assets
- **Total files in data/cache/config/models/results:** 402,916
- **Inventory tree entries:** 406,611 (files + directories)
- **Core corpus + lexicon data:**
  - Files: 401,608
  - Total size: ~6.16 GB (6,158,892,378 bytes)

### Data Asset Distribution
- Raw ingest corpus: 356,529 files
- Augmented corpus: 44,267 files
- Model artifacts: 512 files
- Training splits: 270 files
- Filtered/deduplicated/cleaned corpus: 269 files each (pipeline stages)
- Evaluation artifacts: 15 files
- Pipeline logs: 4 files

### Database Integration Points
- **SQLite touchpoints:** 11 modules
  - Primarily in `src/database/`, `test_database.py`
  - Key module: `src/database/connection.py` (core SQLite adapter)
- **MongoDB touchpoints:** 12 modules
  - `src/database/mongodb_client.py` (dedicated client)
  - `src/augmentation/batch_worker.py` (corpus ingestion)
  - `scripts/migrate_to_mongodb.py` (migration script)
  - Scrapers: `wikipedia.py`, `wikisource.py`, `runner.py`

---

## 🎯 Top 20 Highest-Impact Modules for Extraction

### Scraping Modules (Source Ingestion)
1. **src/scraping/archive_org.py** — Internet Archive scraper
2. **src/scraping/newspaper.py** — Historical newspaper scraper
3. **src/scraping/wikipedia.py** — Western Armenian Wikipedia (with MongoDB integration)
4. **src/scraping/wikisource.py** — Wikisource corpus extraction
5. **src/scraping/loc.py** — Library of Congress scraper
6. **src/scraping/hathitrust.py** — HathiTrust digital library
7. **src/scraping/culturax.py** — CulturaX dataset ingestion
8. **src/scraping/nayiri.py** — Nayiri dictionary scraper (known broken, deferred)
9. **src/scraping/eastern_armenian.py** — Eastern Armenian filtering
10. **src/scraping/metadata_tagger.py** — Source metadata enrichment
11. **src/scraping/frequency_aggregator.py** — Lexicon frequency aggregation

### Corpus Processing Modules
12. **src/augmentation/corpus_vocabulary_builder.py** — Core lexicon builder
13. **src/augmentation/batch_worker.py** — Parallel corpus processor (MongoDB + filesystem)
14. **src/augmentation/runner.py** — Augmentation pipeline orchestrator
15. **src/cleaning/normalizer.py** — Western Armenian normalization (grapheme rules)
16. **src/cleaning/language_filter.py** — Western vs. Eastern dialect classifier
17. **src/cleaning/dedup.py** — MinHash deduplication
18. **src/cleaning/author_database.py** — Author metadata extraction

### Phonetics/Linguistics
19. **src/cleaning/armenian_tokenizer.py** — Armenian tokenization rules
20. **src/augmentation/dialect_distance.py** — Western-Eastern dialect divergence metrics

---

## 🗄️ Database Architecture

### SQLite Usage
- **Primary DB:** `src/armenian_cards.db` (3.4 MB)
- **Connection manager:** `src/database/connection.py`
- **Schema:** Vocabulary cards, frequency lists, metadata
- **Modules:** 11 files touch SQLite (mostly in `src/database/`)

### MongoDB Usage
- **Client:** `src/database/mongodb_client.py` (full-featured corpus document store)
- **Collections:** `documents`, `metadata`
- **Integration points:** 12 modules
- **Use case:** Distributed corpus storage (optional, filesystem fallback available)

**Status:** Dual-storage strategy (SQLite for structured vocab, MongoDB for unstructured corpus)

---

## 🚧 Immediate Blockers & Risks

### ✅ No Critical Blockers
All four requested export artifacts generated successfully:
- ✅ `inventory_tree.txt` (27.5 MB, 406k+ entries)
- ✅ `code_modules.csv` (96 modules classified)
- ✅ `data_assets.csv` (402k+ files, 39 MB report)
- ✅ `dependency_map.txt` (requirements + internal imports + DB usage)

### ⚠️ Known Issues (Not Blocking)
1. **Nayiri dictionary scraper** (`src/scraping/nayiri.py`)
   - Status: Broken (search-based approach fails)
   - Impact: Low (deferred until page-based browsing implemented)
   - Skip for initial migration

2. **Training script instability**
   - `src/training/pretrain.py` exits with code 1
   - Config/checkpoint loading issue (mentioned in user notes)
   - Non-blocking for corpus/scraping extraction

3. **Large corpus size**
   - 356k raw files + 44k augmented = 400k+ documents
   - 6.16 GB compressed; likely 10-15 GB uncompressed
   - Recommendation: Use MongoDB export or selective sampling for initial transfer

4. **Dual database dependencies**
   - Migration target needs both SQLite (for vocab DB) and optional MongoDB support
   - Fallback to filesystem-only mode is available if MongoDB not migrated

### 📋 Recommended Migration Order
1. **Phase 1:** Scraping modules + metadata taggers (11 files)
2. **Phase 2:** Corpus processors (normalizer, dedup, tokenizer) (6 files)
3. **Phase 3:** Database adapters (connection.py, mongodb_client.py) (2 files)
4. **Phase 4:** Vocabulary/lexicon builders (corpus_vocabulary_builder.py, frequency_aggregator.py) (2 files)
5. **Phase 5:** Data migration (selective corpus sampling or full export)

---

## 📦 Export Artifacts Location

All exports saved to: **`migration_exports/`**

```
migration_exports/
├── inventory_tree.txt         # Full workspace file tree (27.5 MB)
├── code_modules.csv           # 96 Python modules with classifications
├── data_assets.csv            # 402k+ data files with size/role
├── dependency_map.txt         # requirements.txt + internal imports + DB usage
├── corpus_fingerprints.csv    # (pre-existing) Source corpus checksums
├── corpus_sources.json        # (pre-existing) Source metadata
├── scraper_matrix.csv         # (pre-existing) Scraper status matrix
├── extraction_boundaries.json # (pre-existing) Module extraction plan
└── MIGRATION_SUMMARY.md       # This file
```

---

## 🔍 Key Insights

### High-Value Extraction Targets
- **11 scraping modules** → 356k raw documents ingested
- **Corpus vocabulary builder** → 6.16 GB processed lexicon + frequency data
- **Dual-DB architecture** → SQLite vocab (3.4 MB) + optional MongoDB corpus
- **Phonetics/morphology signals** → Tokenizer, normalizer, dialect distance

### Minimal Coupling
- Most scrapers are **standalone** (no cross-module dependencies)
- `src/augmentation/` depends on `src/cleaning/` (normalizer, tokenizer)
- Database modules are **adapters** (isolated from business logic)
- Good extraction boundary: **src/scraping/** + **src/cleaning/** + **src/augmentation/** + **src/database/connection.py**

### No Show-Stoppers
- Code is read-only stable (no runtime modifications needed)
- All dependencies documented in `requirements.txt` (torch, transformers, requests, beautifulsoup4, pymongo, etc.)
- Training instability is **separate concern** (not blocking corpus/scraper migration)

---

**Migration Readiness: ✅ GREEN**  
All critical modules identified, inventoried, and classified. No blockers for extraction to unified platform.
