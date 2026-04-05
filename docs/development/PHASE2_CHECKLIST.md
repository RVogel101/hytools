# Phase 2 Implementation Checklist (armenian-corpus-core)

This file is the concrete PR-ready checklist requested by the user.

## 1. Clarify hybrid profile (conflict resolution)

- [x] Definition: Hybrid profile is a configurable `ingestion` mode that combines: corpus-derived stats + external reference lexicons + quality signals (WA/EA score, source type). It resolves cross-source inconsistency by weighting documents and/or rules. Hybrid profile is useful to avoid brittle behavior when one parser or source is noisy, and enables gradual ensemble-based calibration in place of hard "east/west" decisions.
- [x] Useful because it enables stable dataset harmonization across different source reliability and dialect distribution. It can reduce noise from OCR-heavy sources and enforce Western Armenian priority.
- [x] Code reference: `hytools/ingestion/aggregation/frequency_aggregator.py`, `hytools/ingestion/_shared/helpers.py` (source weights), `hytools/ingestion/enrichment/metadata_tagger.py` (language branch classification).
- [x] Config in `config/settings.yaml` section under `ingestion.frequency_aggregator.hybrid_profile`.
- [x] Tested: `tests/test_frequency_aggregator.py::test_hybrid_profile_affects_weights`.

### Issue title
- Completed.

## 2. Incremental merge pipeline

- [x] Add stage in `ingestion.runner` called `incremental_merge` or `ingestion.aggregation.incremental_merge`.
- [x] Behavior: query MongoDB for changed docs since `metadata.last_modified` (or `metadata.ingestion_date`), process only deltas, update downstream collections (`word_frequencies`, `word_frequencies_facets`, `metadata` stats).
- [x] Code ref: `hytools/ingestion/aggregation/frequency_aggregator.py`, `hytools/ingestion/runner.py`, `hytools/ingestion/aggregation/incremental_merge.py`.
- [x] Tested: 4 tests in `tests/test_frequency_aggregator.py` (add/update/delete/scope-change).
- [ ] Integration test proving full rebuild → delta ingest → idempotent re-run cycle (`tests/test_integration_aggregation.py`).

### Issue title
- Completed (integration proof remaining).

## 3. Export formats

- [x] Export module: `hytools/ingestion/aggregation/corpus_export.py`.
- [x] Support output formats:
  - parquet via `pyarrow` / `pandas.DataFrame.to_parquet`
  - HuggingFace dataset via `datasets.Dataset.from_list`.
  - Deterministic release splits (train/validation/test) with seed-based bucketing.
- [x] CLI entry: `corpus_export` registered in `ingestion/runner.py`; also usable standalone.
- [x] Release command: `python -m hytools.ingestion.runner release --config config/settings.yaml --output data/releases/latest`.
- [x] Tested: `tests/test_doctor_and_corpus_export.py`.
- [ ] Integration test asserting byte-identical Parquet output for same corpus state.

### Issue title
- Completed (deterministic export proof remaining).

## 4. Tests and CI

- [x] Tests in `tests/test_frequency_aggregator.py` for branch filter and hybrid profile.
- [x] Data fixture with `metadata.internal_language_branch` values.
- [x] Expected output assertions in `word_frequencies` collections.
- [x] CI workflow `.github/workflows/ci.yml` runs `pytest tests/ -v` on push/PR (Python 3.10–3.12 matrix).
- [ ] Integration scenario for rebuild → delta → idempotent cycle.

### Issue title
- Completed (integration scenario remaining).

## 5. Docs cleanup & backlog

- [x] Mark Phase 1 completed on README
- [x] Add root backlog sheet `docs/development/CURRENT_BACKLOG.md`
- [x] Keep one canonical Quick Start:
  - `docs/QUICK_START_PHASE1.md` is canonical.
  - README points to the canonical quick start.
- [x] Add canonical workflow doc `docs/development/DEVELOPMENT.md`
- [x] Sync `docs/development/FUTURE_IMPROVEMENTS.md` with the status table and current backlog pointer.

### Issue title
- `#xxx: docs cleanup and canonical quick start unification`
