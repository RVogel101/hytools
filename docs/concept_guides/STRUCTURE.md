# armenian-corpus-core — Package Structure

## Top-level layout

Packages are at **repository root** (no `armenian_corpus_core/` directory). The installable package name is `armenian-corpus-core`; `pyproject.toml` discovers `cleaning`, `ingestion`, `research`, `augmentation`, `core_contracts`, `integrations`, `linguistics`, `ocr`.

```
├── augmentation/           # Data augmentation (LLM + non-LLM strategies)
│   ├── __init__.py
│   ├── runner.py           # CLI: run, estimate, status, metrics, visualize
│   ├── batch_worker.py     # Scan docs, build tasks, run strategies, checkpoint
│   ├── strategies.py       # Paraphrase, continue, topic_write, shuffle, etc.
│   ├── llm_client.py       # Ollama/OpenAI-compatible HTTP client
│   ├── safe_generation.py  # WA-only rejection sampling wrapper
│   ├── baseline_statistics.py
│   ├── metrics_pipeline.py
│   ├── metrics_visualization.py
│   ├── drift_detection.py
│   ├── calibrate_distance_weights.py
│   └── benchmark_dialect_distance.py
├── cleaning/               # Normalization, dedup, language filter
│   ├── __init__.py
│   ├── runner.py
│   ├── run_mongodb.py      # MongoDB-backed cleaning pass
│   ├── language_filter.py
│   ├── dedup.py
│   ├── normalizer.py
│   └── armenian_tokenizer.py
├── core_contracts/         # Shared contracts / types
│   └── __init__.py
├── integrations/
│   ├── __init__.py
│   ├── anki/               # AnkiConnect + card DB
│   └── database/           # MongoDB client, ingestion, GridFS
│       ├── mongodb_client.py
│       ├── (removed) run_ingestion.py
│       └── ...
├── linguistics/            # Language analysis (Option B: phonology, lexicon, dialect, metrics)
│   ├── __init__.py         # Re-exports + backward-compat aliases (phonetics, dialect_classifier, loanword_tracker)
│   ├── stemmer.py
│   ├── transliteration.py
│   ├── fsrs.py
│   ├── phonology/          # Letter→IPA, pronunciation, letter data
│   │   ├── phonetics.py
│   │   └── letter_data.py
│   ├── lexicon/            # Etymology (MongoDB) + loanword detection
│   │   ├── etymology_db.py
│   │   └── loanword_tracker.py
│   ├── dialect/            # Rule-based classifier + quantitative dialect metrics
│   │   ├── dialect_classifier.py
│   │   ├── dialect_distance.py
│   │   ├── dialect_clustering.py
│   │   ├── dialect_pair_metrics.py
│   │   └── variant_pairs_helper.py
│   ├── metrics/            # Augmentation pipeline (validation, vocabulary, text stats)
│   │   ├── validation.py
│   │   ├── vocabulary_filter.py
│   │   ├── text_metrics.py
│   │   └── corpus_vocabulary_builder.py
│   ├── morphology/         # Inflection, difficulty
│   │   ├── core.py, nouns.py, verbs.py, articles.py, detect.py, irregular_verbs.py
│   │   ├── difficulty.py
│   │   └── archive/
│   │       └── grammar_rules.py   # Reference/legacy
│   └── tools/              # CLIs and audits
│       ├── phonetics_audit.py
│       └── import_etymology_from_wiktextract.py
├── ocr/                    # OCR pipeline (Tesseract)
│   ├── __init__.py
│   ├── pipeline.py
│   ├── preprocessor.py
│   ├── postprocessor.py
│   └── tesseract_config.py
├── ingestion/              # Corpus ingestion pipeline (acquisition, extraction, enrichment, aggregation, validation)
│   ├── __init__.py
│   ├── runner.py           # Unified CLI: run, status, list, dashboard (python -m ingestion.runner)
│   ├── research_runner.py  # Author/book pipeline: extraction → enrichment → timeline → coverage (python -m ingestion.research_runner)
│   ├── _shared/            # Shared utilities
│   │   ├── __init__.py
│   │   ├── helpers.py      # MongoDB, WA filter, wikitext, logging
│   │   ├── metadata.py     # TextMetadata, Dialect, Region enums
│   │   ├── mappers.py      # Row -> DocumentRecord / LexiconEntry
│   │   ├── data_sources.py # get_news_documents, get_news_sources
│   │   ├── registry.py     # Extraction tool registry
│   │   └── research_config.py  # get_research_config (exclude_dirs, error_threshold_pct)
│   ├── acquisition/        # External sources -> MongoDB
│   │   ├── __init__.py
│   │   ├── wiki.py         # Wikipedia (WA/EA) + Wikisource
│   │   ├── archive_org.py
│   │   ├── hathitrust.py
│   │   ├── gallica.py
│   │   ├── loc.py
│   │   ├── dpla.py
│   │   ├── news.py         # Diaspora newspapers + EA agencies + RSS
│   │   ├── culturax.py
│   │   ├── english_sources.py
│   │   ├── nayiri.py
│   │   ├── gomidas.py
│   │   ├── mechitarist.py
│   │   ├── agbu.py
│   │   ├── ocr_ingest.py
│   │   └── mss_nkr.py
│   ├── discovery/          # Catalog search, book inventory, author extraction/research
│   │   ├── __init__.py
│   │   ├── worldcat_searcher.py
│   │   ├── book_inventory.py
│   │   ├── book_inventory_runner.py
│   │   ├── author_research.py
│   │   ├── author_extraction.py
│   │   └── migrate_book_inventory.py   # JSONL -> MongoDB migration CLI
│   ├── extraction/         # Other stores -> MongoDB
│   │   ├── __init__.py
│   │   └── import_anki_to_mongodb.py
│   ├── enrichment/        # MongoDB -> MongoDB (backfill, views, biography)
│   │   ├── __init__.py
│   │   ├── metadata_tagger.py
│   │   ├── materialize_dialect_views.py
│   │   └── biography_enrichment.py
│   ├── aggregation/        # MongoDB -> derived collections (summaries, coverage, timeline)
│   │   ├── __init__.py
│   │   ├── frequency_aggregator.py
│   │   ├── word_frequency_facets.py
│   │   ├── summarize_unified_documents.py
│   │   ├── coverage_analysis.py
│   │   └── timeline_generation.py
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── validate_contract_alignment.py
│   │   └── export_corpus_overlap_fingerprints.py
│   └── tools/            # ingestion-side CLIs (e.g. GridFS upload)
│       ├── __init__.py
│       └── upload_sources_to_gridfs.py
├── config/
│   └── settings.yaml
├── tests/
├── docs/
└── pyproject.toml
```

## Architecture principles

1. **Ingestion is organized by function** — `ingestion/` has subpackages: `_shared` (helpers, metadata, mappers, registry, research_config), `acquisition` (wiki, archive_org, loc, news, etc.), `discovery` (worldcat_searcher, book_inventory, book_inventory_runner, author_research, author_extraction), `extraction` (import_anki_to_mongodb), `enrichment` (metadata_tagger, materialize_dialect_views, biography_enrichment), `aggregation` (frequency_aggregator, word_frequency_facets, summarize_unified_documents, coverage_analysis, timeline_generation), `validation` (validate_contract_alignment, export_corpus_overlap_fingerprints). Use `ingestion._shared.helpers` for MongoDB, WA filter, wikitext. Author/book pipeline: `ingestion.research_runner`; config: `ingestion._shared.research_config`.
2. **Runner-driven stages** — `ingestion/runner.py` builds the ordered stage list in `_build_stages()` and runs them via dynamic import. Config key: `ingestion` (or `scraping` for backward compatibility). Use `--only` / `--skip` to select stages. Dashboard: `python -m ingestion.runner dashboard`.
3. **MongoDB-first** — Corpus documents, catalogs, metadata, word frequencies, book inventory, and augmentation state live in MongoDB. Config: `database.mongodb_uri`, `database.mongodb_database`.
4. **Post-processing separate** — Enrichment and aggregation stages do not fetch external data; they enrich or aggregate from existing documents.
5. **Augmentation** — `augmentation/runner.py` provides `run`, `estimate`, `status`, `metrics`, `visualize`. Batch worker reads/writes MongoDB when configured; safe_generation and metrics_pipeline are wired via config.

## Adding new acquisition stages

1. Pick the subpackage under `ingestion/`: `acquisition/` (new source), `extraction/`, `enrichment/`, `aggregation/`, or `validation/`.
2. Add a new module (e.g. `ingestion/acquisition/new_source.py`). Implement `run(config: dict) -> None` (and optionally `main()` that loads config and calls `run`). Use `open_mongodb_client(config)` and `insert_or_skip()` from `ingestion._shared.helpers`.
3. Register in `ingestion/runner.py` → `_build_stages()` with the desired position and `supports_mongodb=True` if applicable.
4. For new document sources, add source metadata in `ingestion/enrichment/metadata_tagger.py` SOURCE_METADATA for dialect/region tagging.

## Key entry points

- **Ingestion pipeline:** `python -m ingestion.runner run [--only ...] [--skip ...] [--config config/settings.yaml]` - **Status / dashboard:** `python -m ingestion.runner status`, `python -m ingestion.runner list`, `python -m ingestion.runner dashboard`
- **LOC:** `python -m ingestion.acquisition.loc run`, `python -m ingestion.acquisition.loc catalog --status`
- **Augmentation:** `python -m augmentation.runner run`, `python -m augmentation.runner metrics`, `python -m augmentation.runner visualize`
- **Cleaning:** `python -m cleaning.runner` (or via scraping runner with stage `cleaning`)
- **Research (author/book pipeline):** `python -m ingestion.discovery.book_inventory_runner`, `python -m ingestion.research_runner`
- **GridFS upload (raw PDFs/images):** `python -m ingestion.tools.upload_sources_to_gridfs --path ... --source ...`
- **Book inventory migration:** `python -m ingestion.discovery.migrate_book_inventory`
- **Etymology import (Wiktextract):** `python -m linguistics.tools.import_etymology_from_wiktextract --jsonl ...`
- **OCR page stats / textbook:** `python -m ocr.page_stats <dir>`, `python -m ocr.textbook_modern_wa [pdf]`
- **DPLA API key:** `docs/development/requests_guides/request_dpla_api_key.ps1` or `.sh`

See `docs/concept_guides/MONGODB_CORPUS_SCHEMA.md` for the full MongoDB schema and `docs/concept_guides/DATA_SOURCES_API_REFERENCE.md` for scraper configuration.
