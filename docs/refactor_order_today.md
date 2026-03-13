# Refactor Order Today

Date: 2026-03-06
Mode: Planning timeline only (no code implementation in this step)

## Hour-by-hour schedule

### 09:00-10:00
- Finalize canonical package namespaces:
  - `armenian_corpus_core`
  - `armenian_linguistics_core`
- Freeze public API candidates for first extraction batch:
  - tokenization API
  - metadata enums and `TextMetadata`
- Define no-break rule: existing `src.*` imports must remain valid via temporary shims.

### 10:00-11:00
- Draft contract interfaces in design docs (not code yet):
  - `DocumentProvider`
  - `CorpusWriter`
  - `LinguisticResourceProvider`
- Confirm which current modules are pure domain and which are adapter-bound.

### 11:00-12:00
- Plan Batch 1 extraction details:
  - `src/cleaning/armenian_tokenizer.py`
  - `src/cleaning/normalizer.py`
  - `src/scraping/metadata.py`
- Prepare import rewrite map for direct dependencies of these modules.

### 12:00-13:00
- Risk gate review before first move:
  - config coupling checks
  - DB coupling checks
  - CLI entrypoint dependencies
- Confirm rollback criteria for each extraction batch.

### 13:00-14:00
- Plan Batch 2 extraction details:
  - `src/augmentation/dialect_distance.py`
  - `src/augmentation/dialect_pair_metrics.py`
  - `src/augmentation/text_metrics.py`
- Identify where `src.cleaning.*` imports must be rewritten to linguistics-core imports.

### 14:00-15:00
- Plan Batch 3 extraction details:
  - `ingestion/discovery/book_inventory.py`
  - `ingestion/discovery/author_research.py`
  - `ingestion/aggregation/coverage_analysis.py`
- Separate storage-neutral logic from persistence calls to keep DB adapters local.

### 15:00-16:00
- Define compatibility shim lifespan:
  - introduce shims at start of implementation
  - retain for two green CI cycles
  - remove only after legacy import scan passes
- Define CI checks for forbidden legacy imports after cutover.

### 16:00-17:00
- Final cross-repo alignment meeting checklist (`WesternArmenianLLM` + `lousardzag`):
  - approve enums and DTOs
  - approve adapter contracts
  - approve extraction order and ownership
- Mark go/no-go for implementation day.

## Planned extraction order (implementation day)
1. Linguistics primitives (`tokenizer`, `normalizer`) to reduce downstream churn.
2. Corpus metadata schema (`metadata.py`) to establish shared document contract.
3. Linguistics metrics modules (`dialect_distance`, `text_metrics`, related metrics).
4. Research domain modules (`book_inventory`, `author_research`, `coverage_analysis`).
5. Split mixed modules (`language_filter`, `database/schema`, `database/telemetry`) into core vs adapter slices.
6. Rewrite imports in runners, scrapers, and tests.
7. Remove shims after CI and smoke scripts are green twice.

## Risk checkpoints during execution
- Checkpoint A after step 2: verify metadata enum compatibility with both repos.
- Checkpoint B after step 4: verify no direct DB imports remain in extracted core modules.
- Checkpoint C after step 6: verify all `python -m src.*` commands still run via wrappers.
