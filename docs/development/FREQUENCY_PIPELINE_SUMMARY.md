# Frequency Pipeline Summary

This note consolidates the inspection performed on the Armenian corpus frequency pipeline (aggregation, facets, per-document metrics, tokenization, and runner integration). It lists the key files, functions/classes, how they fit together, configuration knobs, outputs, and suggested next steps.

## Purpose
- Produce a single, ranked word frequency list for Western Armenian (`word_frequencies`).
- Produce multi-dimensional facet counts (`word_frequencies_facets`) for queries by author/source/dialect/year/region.
- Provide per-document metrics (`metadata.document_metrics.word_counts`) used by downstream analytics.

## Key files (locations)
- `ingestion/aggregation/frequency_aggregator.py` — global weighted frequency aggregator (builds `word_frequencies`).
- `ingestion/aggregation/word_frequency_facets.py` — facet aggregation from per-document metrics (builds `word_frequencies_facets`).
- `ingestion/_shared/helpers.py` — ingest helpers and `_compute_document_metrics()` which populates `metadata.document_metrics`.
- `cleaning/armenian_tokenizer.py` — canonical Armenian normalization and tokenization utilities (`extract_words`, `word_frequencies`).
- `ingestion/runner.py` — pipeline runner that registers and runs `frequency_aggregator` as a stage.
- `ingestion/_shared/registry.py` — extraction tool registry that documents and registers `frequency_aggregator` and related tools.

## Function/Class inventory (high level)

- `ingestion/aggregation/frequency_aggregator.py`
  - `SOURCE_WEIGHTS` (dict)
  - `MIN_COUNT` (int)
  - `_source_weight(source: str) -> float`
  - `_get_target_weights(source_doc_counts: dict, target_pcts: dict) -> dict`
  - `_tokenize_armenian(text: str) -> list[str]`
  - `run(config: dict) -> None` — main entry: reads `documents.text`, counts tokens per source, applies weights (fixed or target-weighted), writes `word_frequencies` and metadata.

- `ingestion/aggregation/word_frequency_facets.py`
  - `FACET_TYPES` (tuple)
  - `_get_facet_value(doc: dict, facet: str) -> str | None`
  - `run(config: dict) -> None` — wrapper
  - `run_aggregation(config: dict) -> dict` — read `metadata.document_metrics.word_counts` and aggregate per facet
  - `query(word, facet=None, facet_value=None, config=None, client=None) -> int | list` — query API
  - `run_query_cli(...)` — CLI printer

- `ingestion/_shared/helpers.py`
  - `_get_mongodb_config(config)`, `open_mongodb_client(config)` (context manager)
  - `_compute_document_metrics(text, text_id, source) -> dict | None` — computes `TextMetricCard`, loanword analyses, `word_counts` (Counter)
  - `_check_drift_on_ingest(metrics, metadata, config) -> dict | None` — optional drift detector
  - `insert_or_skip(client, *, source, title, text, url=None, author=None, metadata=None, config=None) -> bool` — insert helper that attaches `document_metrics` when enabled

- `cleaning/armenian_tokenizer.py`
  - `_LIGATURE_MAP`, `_ARMENIAN_WORD_RE`, `MIN_WORD_LENGTH`
  - `decompose_ligatures`, `armenian_lowercase`, `normalize`
  - `extract_words(text, min_length=MIN_WORD_LENGTH) -> list[str]`
  - `word_frequencies(text, min_length) -> Counter`

- `ingestion/runner.py`
  - `Stage` dataclass
  - `_build_stages(cfg) -> list[Stage]` — registers stages including `frequency_aggregator` and `word_frequency_facets`
  - `_run_stage(stage, cfg) -> dict` — import module, call `run(cfg)` or `main()`
  - `run_pipeline(config, only=None, skip=None) -> dict`
  - CLI commands: `run`, `status`, `list`, `dashboard`

- `ingestion/_shared/registry.py`
  - `ToolStatus` enum, `ToolDependency`, `ExtractionToolSpec` dataclasses
  - `ExtractionRegistry` with `_register_default_tools()` including `frequency_aggregator`
  - registry helpers: `get_registry()`, `get_tool_spec()`, `list_all_tools()`, `get_pipeline_execution_order()`

## How the pieces fit (workflow)
1. Acquisition scripts insert documents into MongoDB using `insert_or_skip()` (or runner stages). If enabled, `_compute_document_metrics()` runs at ingest and stores `metadata.document_metrics.word_counts`.
2. Post-processing: the runner (`ingestion.runner`) executes stages in order. `frequency_aggregator.run(config)` reads raw `documents.text` (does not require per-doc metrics) to build a global weighted frequency list written to `word_frequencies`.
3. Optionally, `word_frequency_facets.run_aggregation(config)` reads `metadata.document_metrics.word_counts` (so compute-on-ingest must be enabled) to build `word_frequencies_facets` (facet, facet_value, word, count).
4. Both aggregation stages write a pipeline metadata document into the `metadata` collection (stage name, timestamp, stats, weights_used when target-weighted).

## Configuration knobs
- `config/settings.yaml` controls:
  - `database.compute_metrics_on_ingest` / `scraping.compute_metrics_on_ingest` — compute per-document metrics at ingest.
  - `scraping.frequency_aggregator.target_*_pct` — target-weighted mode for desired source mix (triggers `_get_target_weights`).
- `frequency_aggregator.SOURCE_WEIGHTS` — default fixed per-source weights when target mode not used.
- `MIN_COUNT` — threshold to exclude low-frequency words from `word_frequencies`.

## Collections produced
- `word_frequencies` — unified ranked list (documents with `word`, `total_count`, `source_counts`, `source_count`, `in_nayiri`, `rank`).
- `word_frequencies_facets` — entries: `{facet, facet_value, word, count}` (multi-dimensional counts).
- `metadata` — pipeline run summaries (e.g., `stage: frequency_aggregator`).

## Run / CLI examples
- Run frequency aggregator directly:
```powershell
python -m ingestion.aggregation.frequency_aggregator
```
- Run facet aggregation:
```powershell
python -m ingestion.aggregation.word_frequency_facets aggregate
```
- Run pipeline runner (only aggregator stages):
```powershell
python -m ingestion.runner run --only frequency_aggregator word_frequency_facets
```

## Tests & references
- Tokenization and metrics are referenced in tests such as `tests/test_wa_corpus.py` and `tests/test_loanword_tracker.py` (see repo tests for expectations).
- Docs: `docs/development/SCRAPING_DIRECTORY_AUDIT.md`, `docs/concept_guides/MONGODB_CORPUS_SCHEMA.md` provide context and schema notes.

## Notes, caveats and important behaviors
- `frequency_aggregator` reads `documents.text` directly; it does not require per-document metric computation.
- `word_frequency_facets` requires `metadata.document_metrics.word_counts` to exist — enable `compute_metrics_on_ingest` to populate these.
- Tokenization differences: per-document metrics use `extract_words(min_length=1)` to count even 1-char tokens for diagnostics; global aggregator may filter by a different regex/min length logic.
- Target-weighted mode will compute weights as `target_pct / current_pct` (capped) to bias the combined frequencies toward a desired source mix; pipeline metadata records weights used.

## Next steps (suggested)
1. Export a machine-readable inventory (JSON) of functions and signatures (I can generate this). 
2. Run `frequency_aggregator` on a dev MongoDB instance and sample `word_frequencies` documents to validate tokenization and weighting.
3. If you plan to use these frequencies in `lousardzag` progression, confirm mapping between `word_frequencies.rank` and `lousardzag`'s expected `frequency_rank` field.

---
Generated by inspection on March 21, 2026.
