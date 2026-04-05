# Scripts

These scripts support corpus and research workflows.

- **phonetics_audit.py** — Phonetics validation and Eastern Armenian leakage audit (self-contained).

**audit_eastern_leakage** remains in WesternArmenianLLM as the mandatory pre-training gate (depends on `src.cleaning.language_filter`).

To monitor LOC background downloads, use: `python -m scraping.loc status`

# Armenian Corpus Core

Central package for Armenian language corpus collection, extraction, and normalization. Scrapes all available Western Armenian text content from the internet and stores it in a local MongoDB database.

> NOTE: The package namespace has been migrated to `hytools`. Use `import hytools` and `from hytools.xxx import ...` APIs. Original top-level package names are removed.

**Version**: 0.1.0-alpha  
**Status**: 🟡 Pilot (batch 7 of comprehensive migration)

## Overview

`armenian-corpus-core` is a domain-neutral package that serves as the single source of truth for:

- **Core Contracts**: `DocumentRecord`, `LexiconEntry`, `PhoneticResult` (frozen dataclasses)
- **Extraction Pipeline**: 8 modular ETL tools (export, ingest, validate, merge, materialize)
- **Normalization utilities**: NFKC Unicode normalization, content hashing, deduplication
- **Registry & CLI**: Tool discovery, execution orchestration, CI/CD integration

## Architecture

```

```

## Extraction Pipeline

After scraping, the extraction pipeline processes MongoDB data through these stages:

### 1. Import Vocabulary Data
Imports vocabulary data into MongoDB.

### 2. Validate Contract Alignment
Validates data integrity: required fields, internal_language_code and internal_language_branch tags, source distribution.

### 3. Detect Near-Duplicates
Analyzes `normalized_content_hash` fields to find near-duplicate documents across sources.

### 4. Materialize Language Branch Views
Tags each document with `internal_language_branch` (western_armenian/eastern_armenian/mixed/unknown) for fast filtered queries.

### 5. Build Frequency List
Aggregates per-source word frequencies, applies source weights, stores in MongoDB `word_frequencies` collection.

### 6. Summarize Corpus
Generates summary statistics (counts by source, internal_language_branch, text size) stored in MongoDB `metadata` collection.

All stages read from and write to MongoDB — no intermediate CSV, JSONL, or file-based I/O.

---

## Full Pipeline Execution

Primary quick start: `docs/QUICK_START_PHASE1.md`

Canonical workflow and command reference: `docs/development/DEVELOPMENT.md`

Current active backlog: `docs/development/CURRENT_BACKLOG.md`

### Local (Canonical Runner)

```bash
# Run the full pipeline (scraping + extraction + post-processing)
python -m hytools.ingestion.runner run --config config/settings.yaml

# Run only scraping stages
python -m hytools.ingestion.runner run --config config/settings.yaml --group scraping

# Run only extraction stages
python -m hytools.ingestion.runner run --config config/settings.yaml --group extraction

# Run only post-processing stages
python -m hytools.ingestion.runner run --config config/settings.yaml --group postprocessing

# Skip specific stages
python -m hytools.ingestion.runner run --config config/settings.yaml --skip validate_contract_alignment

# Run one specific stage
python -m hytools.ingestion.runner run --config config/settings.yaml --only news

# List all registered stages
python -m hytools.ingestion.runner list --config config/settings.yaml

# Preflight the configured run without executing stages
python -m hytools.ingestion.runner run --config config/settings.yaml --dry-run

# Run in background
python -m hytools.ingestion.runner run --config config/settings.yaml --background

# Build the dashboard
python -m hytools.ingestion.runner dashboard --config config/settings.yaml --output data/logs/scraper_dashboard.html
```

### Wrapper Script

```bash
# Run scrape + OCR + clean + ingest through the repo-level wrapper
python scripts/run_pipeline.py --stage all --config config/settings.yaml
```

### CI/CD (GitHub Actions)

Recommended automation setup:

- Run `python -m hytools.ingestion.runner run --config config/settings.yaml --group scraping` from CI scraping workflows.
- Use `--group extraction` to run only extraction stages in CI extraction jobs.
- Persist `data/logs/pipeline_summary.json` as the pipeline summary artifact.
- Add schedule/dispatch triggers for automated scraping runs.

---

## Core Contracts

### DocumentRecord

```python
@dataclass(frozen=True)
class DocumentRecord:
    document_id: str              # Unique identifier
    source_family: str            # anki_sentences, wikipedia, etc.
    text: str                     # Content (may be empty for fingerprints)
    content_hash: str             # NFKC-normalized SHA256
    dialect_tag: DialectTag       # WESTERN_ARMENIAN, EASTERN_ARMENIAN, etc.
    metadata: dict[str, Any]      # Flexible metadata
```

### LexiconEntry

```python
@dataclass(frozen=True)
class LexiconEntry:
    lemma: str                    # Headword
    translation: str              # English translation
    pos: str                      # Part of speech
    pronunciation: str            # IPA or phonetic annotation
    frequency_rank: int           # Rank in corpus
    syllable_count: int           # Syllable count
    internal_language_code: str | None  # Internal language code (e.g., 'hyw' or 'hye')
    internal_language_branch: str | None  # Internal language branch (e.g., 'western_armenian' or 'eastern_armenian')
    metadata: dict[str, Any]      # Flexible metadata
```

### PhoneticResult

```python
@dataclass(frozen=True)
class PhoneticResult:
    word: str                     # Input word
    ipa: str                      # IPA transcription
    english_approx: str           # English approximation
    max_phonetic_difficulty: int  # 1-5 difficulty score
    metadata: dict[str, Any]      # Flexible metadata
```

---

## Tool Registry

Query available tools and their metadata:

```python
from scraping.registry import get_registry, get_tool_spec, list_all_tools

tools = list_all_tools()

spec = get_tool_spec("validate_contract_alignment")
print(spec.description)  # "Validate corpus data integrity in MongoDB"
print(spec.inputs)       # ["MongoDB documents collection"]
print(spec.outputs)      # ["MongoDB metadata collection (validation report)"]
```

---

## Integration

### WesternArmenianLLM

The WesternArmenianLLM project reads training data from the MongoDB database populated by this project's scrapers.

```python
from core_contracts import DocumentRecord, LexiconEntry
from scraping.registry import get_tool_spec

tool_spec = get_tool_spec("validate_contract_alignment")
print(f"Using tool: {tool_spec.description}")
```

---

## Development

### Installation (Editable)

```bash
cd /path/to/armenian-corpus-core
pip install -e .
```

### Quick start

- Canonical quick start workflow is in `docs/QUICK_START_PHASE1.md`.

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
black armenian_corpus_core/ && isort armenian_corpus_core/
mypy armenian_corpus_core/
```

---

## Roadmap

### Phase 1 (Current - Batch 7): Foundation

- ✅ Package scaffolding (setup.py, pyproject.toml)
- ✅ Extraction tool registry
- ✅ CI/CD workflow
- ✅ Pipeline orchestration
- ✅ Move core contracts to central package

### Phase 2: Enhancement (active)

- ✅ Implement `hybrid` profile for statistical conflict resolution
- ✅ Add incremental merge (only re-process changed records)
- ✅ Create format exporters (parquet, HuggingFace datasets)
- ✅ Add comprehensive test suite + CI workflow
- [ ] Integration-test proof (delta idempotency, deterministic export)
- [x] Unified review & audit layer operational baseline (shared queue, linguistics-owned heuristics, review CLI)

### Phase 3: Distribution

- Publish to PyPI / internal package repo
- Create documentation site
- Add performance benchmarks

---

## Status & Support

**Current Status**: 🟡 Alpha (Batch 7)  
**Stability**: Extraction pipeline validated with 42K+ real records  
**Breaking Changes**: Possible in alpha releases  
**Support**: Issues and PRs welcome

---

## File Manifest

**Package Files**:

- `armenian_corpus_core/__init__.py` — Package metadata and version
- `setup.py` — setuptools installation configuration
- `pyproject.toml` — Modern Python packaging (PEP 517)

**Core Contracts**:

- `armenian_corpus_core/core_contracts/__init__.py` — Contract exports
- `armenian_corpus_core/core_contracts/types.py` — Domain dataclasses
- `armenian_corpus_core/core_contracts/hashing.py` — Text normalization and hash helpers


 `ingestion/extraction/import_anki_to_mongodb.py` — AnkiConnect → MongoDB import
- `scraping/summarize_unified_documents.py` — Corpus summary statistics
- `scraping/frequency_aggregator.py` — Word frequency aggregation
- `scraping/metadata_tagger.py` — Source metadata enrichment

---

## References

- **WesternArmenianLLM**: Companion project for model training
- **Core Contracts**: Data types defined in `core_contracts/types.py`

