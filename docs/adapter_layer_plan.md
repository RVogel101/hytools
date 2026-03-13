# Adapter Layer Plan

Date: 2026-03-06
Scope: Planning only (no code movement yet)

## Objective
Define a stable adapter layer so both `WesternArmenianLLM` and `lousardzag` consume the same central source of truth from:
- `armenian-corpus-core`
- `armenian-linguistics-core`

## Boundary Decision Summary

### Move to `armenian-corpus-core`
- Corpus metadata model and enums currently in `src/scraping/metadata.py`
- Metadata tagging logic in `src/scraping/metadata_tagger.py`
- Research domain models and analysis logic in `ingestion/discovery/*.py`, `ingestion/enrichment/biography_enrichment.py`, `ingestion/aggregation/*.py` (except project-only test scripts)
- Storage-neutral schema contracts from `src/database/schema.py`
- Storage-neutral telemetry event model from `src/database/telemetry.py`

### Move to `armenian-linguistics-core`
- Tokenization and normalization from `src/cleaning/armenian_tokenizer.py` and `src/cleaning/normalizer.py`
- Dialect distance, clustering, pair metrics, and metric cards from `src/augmentation/dialect_*.py` and `src/augmentation/text_metrics.py`
- Baseline, drift, and calibration logic from `src/augmentation/baseline_statistics.py`, `src/augmentation/drift_detection.py`, `src/augmentation/calibrate_distance_weights.py`
- Dialect benchmark logic from `src/augmentation/benchmark_dialect_distance.py`

### Keep local as adapters in `WesternArmenianLLM`
- All source connectors in `src/scraping/` that call remote systems (Wikipedia, LOC, Archive, etc.)
- Storage engines and migration runners in `src/database/connection.py`, `src/database/mongodb_client.py`, `src/database/runner.py`, `src/database/orchestrator.py`
- App runtime layers: `src/serving/`, `src/training/`, `src/cloud/`, `src/rag/`, `src/ocr/`, `spaces_app.py`
- Local CLI and orchestration wrappers in `src/*/runner.py`

### Keep local as adapters in `lousardzag`
- Phonetics source adapter exposing lousardzag phoneme inventory to linguistics-core contracts
- Orthography/transliteration adapter mapping lousardzag conventions to shared token model
- Lexicon/pronunciation lookup adapter mapped to corpus-core metadata and provenance contracts

## Proposed Adapter Contracts

### Contract 1: Document Provider
Purpose: core pipelines consume documents without file-path assumptions.

Input:
- Iterable of `DocumentRecord` objects (text + metadata)

Implemented by:
- `WesternArmenianLLM` filesystem/corpus adapters
- `lousardzag` dataset adapters

### Contract 2: Corpus Writer
Purpose: decouple core ingestion from SQLite/Mongo implementations.

Methods:
- `upsert_document(record)`
- `record_ingestion_event(event)`
- `record_quality_metrics(metrics)`

Implemented by:
- `WesternArmenianLLM` SQLite adapter
- `WesternArmenianLLM` Mongo adapter
- Optional lousardzag persistence adapter

### Contract 3: Linguistic Resource Provider
Purpose: allow shared scoring engines to consume marker lists, variant maps, and optional author lists.

Methods:
- `get_marker_set(version)`
- `get_variant_pairs(version)`
- `get_author_features(dialect)`

Implemented by:
- `WesternArmenianLLM` static resource adapter
- `lousardzag` phonetics/lexicon adapter

## Import Rewrite Strategy

### Phase A: Compatibility-first
- Add thin re-export shims under existing `src` paths.
- Keep old import paths valid while introducing new core packages.
- Freeze public symbols for each extracted module before rewrites.

### Phase B: Batch rewrites by subsystem
- Batch 1: tokenization + linguistics metrics imports.
- Batch 2: metadata + research pipeline imports.
- Batch 3: telemetry/schema imports.
- Rewrite scripts and tests last, after module-level imports are stable.

### Phase C: Legacy import shutdown
- Add CI check that fails on `from src.cleaning.armenian_tokenizer` and similar legacy imports.
- Remove shim modules after two clean CI runs.

## Risk List

1. High: Core modules currently read `config/settings.yaml` directly.
Mitigation: move config loading to adapters; pass validated config into core constructors.

2. High: DB-specific classes are imported inside scraping and research paths.
Mitigation: route writes through `CorpusWriter` ports; keep DB classes local.

3. Medium: Dialect scoring mixes reusable rules with local author/city lists.
Mitigation: split scoring engine from resource providers and publish versioned marker sets.

4. Medium: Runner scripts depend on `python -m src.*` paths.
Mitigation: preserve old entry points as wrappers until migration ends.

5. Medium: Two repos may diverge on enum naming (`Dialect`, `Region`, `SourceType`).
Mitigation: define shared canonical enums in corpus-core first and lock schema version.

6. Low: Migration sequencing may break active experiments.
Mitigation: perform extraction in branch windows and keep backward-compatible releases.

## Definition of Done for Planning Stage
- Boundaries approved for both core packages.
- Adapter contracts approved by both repos.
- Import rewrite order approved and linked to CI gating.
- Risks acknowledged with owner and mitigation path.
