# Code moved from WesternArmenianLLM

The following packages and scripts were moved from **WesternArmenianLLM** so that repo can focus solely on **directly training** the model. Data collection, OCR, research, and augmentation live here.

## Status of moved items

| Item | Documented location | Actual location | Status |
|------|---------------------|-----------------|--------|
| **ocr/** | `armenian_corpus_core/ocr/` | `ocr/` (repo root) | ✅ Moved; package at root |
| **research/** | `armenian_corpus_core/research/` | **`ingestion/`** (discovery, enrichment, aggregation, research_runner, _shared/research_config) | ✅ Moved under ingestion; no top-level `research/` |
| **augmentation/** | `armenian_corpus_core/augmentation/` | `augmentation/` (repo root) | ✅ Moved; package at root |
| **phonetics_audit.py** | `scripts/phonetics_audit.py` | `linguistics/phonetics_audit.py` | ✅ Moved; lives under linguistics |
| **SQLite / DB code** | `armenian_corpus_core.integrations.database` | `integrations/database/` (mongodb_client, run_ingestion, etc.) | ✅ Present; no `armenian_corpus_core` prefix in this repo |
| **migration_exports/** | `migration_exports/` | Referenced in doc and phonetics_audit; pyproject excludes it from packages | ✅ Canonical dir for this repo |
| **armenian_cards.db** | `data/anki/` | `data/anki/` (when used) | ✅ Documented |
| **test_author_research.py** etc. (second pass) | `tests/` | `tests/test_author_research.py`, `test_dialect_distance.py`, `test_drift_detection.py` | ✅ Present |
| **Third-pass tests** | `tests/` | `tests/test_eastern_armenian_news.py`, `test_baseline_statistics.py`, `test_corpus_vocabulary_filter.py`, `test_dialect_pair_metrics.py`, `test_worldcat_searcher.py` | ✅ Present |
| **Fourth-pass tests** | `tests/` | `tests/test_phase1_eastern_prevention.py`, `test_augmentation_validation.py`, `test_metadata_tagging.py`, `test_book_inventory.py`, `test_metrics_pipeline.py`, `test_metrics_visualization.py`, `test_variant_pairs_helper.py`, `test_text_metrics.py`, `test_ocr.py`, `test_database_pipeline.py` | ✅ Present |
| **phonetics_rule_gaps.md** | WA-LLM `migration_exports/` → here | `docs/phonetics_rule_gaps.md` | ✅ Present |
| **LOC scraper / status** | `scraping/loc.py` | `scraping/loc.py` (run, status, catalog) | ✅ Present |
| **LOC logs** | gitignored in WA-LLM | `data/logs/loc_background_errors.log` etc. | ✅ Belong here |
| **SCRAPER_IMPLEMENTATION_STATUS.md** | WA-LLM → here | `docs/SCRAPER_IMPLEMENTATION_STATUS.md` | ✅ Present |

**Note:** This repo uses **flat packages at root** (e.g. `ingestion/`, `scraping/`, `ocr/`, `augmentation/`, `linguistics/`, `integrations/`) as defined in `pyproject.toml`. Research/author-book pipeline lives under `ingestion/` (discovery, enrichment, aggregation, research_runner). There is no top-level `armenian_corpus_core/` directory; the package name is `armenian-corpus-core` and the discoverable packages are the root-level ones.

---

## Packages (under repo root)

- **ocr/** — OCR pipeline (PDF -> clean text). Originally `src/ocr`.
- **research (now under ingestion/)** — Author/book research and metadata enrichment (author extraction, biography, timeline, coverage). Modules: `ingestion/discovery/` (author_extraction, author_research, book_inventory, book_inventory_runner, worldcat_searcher), `ingestion/enrichment/biography_enrichment.py`, `ingestion/aggregation/coverage_analysis.py`, `ingestion/aggregation/timeline_generation.py`, `ingestion/research_runner.py`, `ingestion/_shared/research_config.py`. Originally `src/research`, then `research/` at root; now under `ingestion/`.
- **augmentation/** — Data augmentation (LLM and non-LLM strategies, batch worker). Originally `src/augmentation`.

**Import note:** These modules may still reference `src.*` (e.g. `src.cleaning.language_filter`, `src.config_loader`). To run them standalone from this repo, either:

- Set `PYTHONPATH` to include the WesternArmenianLLM root, or
- Refactor imports to use local equivalents where available (e.g. `cleaning.*`, `scraping.*`).

## Scripts and related

- **phonetics_audit.py** — Lives in `linguistics/phonetics_audit.py` (phonetics validation and Eastern Armenian leakage audit). Not under `scripts/`.

**audit_eastern_leakage** remains in WesternArmenianLLM as the mandatory pre-training gate (depends on `src.cleaning.language_filter`).

## Database / ingestion

WesternArmenianLLM no longer performs scraping or ingestion. All corpus data is read from **MongoDB**. This repo (armenian-corpus-core) owns ingestion and data-processing pipelines; WesternArmenianLLM consumes from the central DB and runs cleaning/splits/training only.

- **SQLite ingestion (connection, schema, migrator, cleanup, telemetry, adapters):** In `integrations/database/` in this repo. Removed from WesternArmenianLLM; WA-LLM `src/database` now has only validator, runner, mongodb_reader, targets.
- **migration_exports:** Canonical directory is `migration_exports/` in this repo (see README there). WA-LLM `.gitignore` excludes `migration_exports/`.
- **armenian_cards.db:** Lives in `data/anki/` for Anki-based extraction. WA-LLM does not use local `.db` files.

## Second pass (tests, phonetics doc, LOC)

- **Tests:** `test_author_research.py`, `test_dialect_distance.py`, `test_drift_detection.py` were moved from WesternArmenianLLM `tests/` to this repo's `tests/`.
- **Additional tests (third pass):** `test_eastern_armenian_news.py`, `test_baseline_statistics.py`, `test_corpus_vocabulary_filter.py`, `test_dialect_pair_metrics.py`, `test_worldcat_searcher.py` were moved from WesternArmenianLLM to this repo's `tests/`.
- **Phonetics doc:** `phonetics_rule_gaps.md` was moved from WA-LLM `migration_exports/` to `docs/phonetics_rule_gaps.md`. It documents phonetics rule gaps not used in WA-LLM training.
- **Additional tests (fourth pass):** The following were moved from WesternArmenianLLM to this repo's `tests/`: `test_phase1_eastern_prevention.py`, `test_augmentation_validation.py`, `test_metadata_tagging.py`, `test_book_inventory.py`, `test_metrics_pipeline.py`, `test_metrics_visualization.py`, `test_variant_pairs_helper.py`, `test_text_metrics.py`, `test_ocr.py`, `test_database_pipeline.py`. WesternArmenianLLM now keeps only `test_cleaning.py` (training-relevant).
- **LOC / scraper artifacts:** LOC progress monitoring is now integrated into `scraping/loc.py` (run `python -m scraping.loc status`). `loc_download.log` and `loc_background_job_errors.log` are gitignored in WesternArmenianLLM; LOC scraper and logs belong here.
- **Scraper doc:** `docs/SCRAPER_IMPLEMENTATION_STATUS.md` was moved from WesternArmenianLLM to this repo (shortened; full history in git). WesternArmenianLLM has no scraper implementation.
