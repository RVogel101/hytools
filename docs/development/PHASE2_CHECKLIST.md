# Phase 2 Implementation Checklist (armenian-corpus-core)

This file is the concrete PR-ready checklist requested by the user.

## 1. Clarify hybrid profile (conflict resolution)

- [ ] Definition: Hybrid profile is a configurable `ingestion` mode that combines: corpus-derived stats + external reference lexicons + quality signals (WA/EA score, source type). It resolves cross-source inconsistency by weighting documents and/or rules. Hybrid profile is useful to avoid brittle behavior when one parser or source is noisy, and enables gradual ensemble-based calibration in place of hard "east/west" decisions.
- [ ] Useful because it enables stable dataset harmonization across different source reliability and dialect distribution. It can reduce noise from OCR-heavy sources and enforce Western Armenian priority.
- [ ] Code reference: `hytools/ingestion/aggregation/frequency_aggregator.py`, `hytools/ingestion/_shared/helpers.py` (source weights), `hytools/ingestion/enrichment/metadata_tagger.py` (language branch classification).
- [ ] Add config in `config/settings.yaml` section under `ingestion.frequency_aggregator.hybrid_profile`.

### Issue title
- `#xxx: implement hybrid frequency_aggregator profile (source-weighted + WA/EA conflict resolution)`

## 2. Incremental merge pipeline

- [ ] Add stage in `ingestion.runner` called `incremental_merge` or `ingestion.aggregation.incremental_merge`.
- [ ] Behavior: query MongoDB for changed docs since `metadata.last_modified` (or `metadata.ingestion_date`), process only deltas, update downstream collections (`word_frequencies`, `word_frequencies_facets`, `metadata` stats).
- [ ] Code ref: `hytools/ingestion/aggregation/frequency_aggregator.py`, `hytools/ingestion/runner.py`, `hytools/ingestion/aggregation/word_frequency_facets.py`.

### Issue title
- `#xxx: add incremental merge stage to ingestion runner (delta processing)`

## 3. Export formats

- [ ] Create export module, e.g. `hytools/ingestion/tools/export_word_frequencies.py`.
- [ ] Support output formats:
  - parquet via `pyarrow` or `pandas.DataFrame.to_parquet`
  - HuggingFace dataset via `datasets.Dataset.from_pandas`.
  - JSONL for streaming and compatibility.
- [ ] Add CLI entry in `ingestion/runner.py` or top-level script.
- [ ] Add docs in `docs/development/EXPORT_FORMATS.md` and update README usage section.

### Issue title
- `#xxx: add word frequency export to parquet and HF datasets`

## 4. Tests and CI

- [ ] add new tests in `tests/test_frequency_aggregator.py` for branch filter and hybrid profile
  - data fixture with `metadata.internal_language_branch` values.
  - expected output in `word_frequencies` as collections.
- [ ] add integration scenario for partial pipeline (metadata_tagger -> frequency_aggregator -> facets).
- [ ] ensure coverage in CI workflow (GH actions) by adding or updating `python -m pytest tests/` in `/.github/workflows/`.

### Issue title
- `#xxx: expand test suite for frequency_aggregator incremental + branch filters`

## 5. Docs cleanup & backlog

- [ ] Mark Phase 1 completed on README (done)
- [ ] Add root backlog sheet `docs/development/CURRENT_BACKLOG.md` (done)
- [ ] Keep one canonical Quick Start:
  - `docs/QUICK_START_PHASE1.md` is canonical.
  - Add note in README: "Primary Quick Start at `docs/QUICK_START_PHASE1.md`."
- [ ] Sync `docs/development/FUTURE_IMPROVEMENTS.md` with the status table (Phase 2 moved to active, current backlog pointer).

### Issue title
- `#xxx: docs cleanup and canonical quick start unification`
