# Armenian Corpus Core

Central package for canonical Armenian language corpus contracts, extraction, and normalization utilities. Provides unified interfaces for both **Lousardzag** (Anki learning) and **WesternArmenianLLM** (corpus scraping) projects.

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
armenian-corpus-core/
├── pyproject.toml              # Build configuration
├── armenian_corpus_core/
│   ├── __init__.py             # Package metadata
│   ├── core_contracts/
│   │   ├── __init__.py
│   │   ├── types.py            # DocumentRecord, LexiconEntry, PhoneticResult
│   │   └── hashing.py          # NFKC normalization and hashing helpers
│   └── extraction/
│       ├── __init__.py
│       ├── registry.py         # Tool registry & invocation interface
│       ├── run_extraction_pipeline.py  # Orchestration script
│       ├── mappers.py
│       ├── export_core_contracts_jsonl.py (Batch 2)
│       ├── validate_contract_alignment.py (Batch 3)
│       ├── ingest_wa_fingerprints_to_contracts.py (Batch 4)
│       ├── merge_document_records.py (Batch 5)
│       ├── merge_document_records_with_profiles.py (Batch 6)
│       ├── extract_fingerprint_index.py (Batch 6)
│       ├── materialize_dialect_views.py (Batch 6)
│       └── summarize_unified_documents.py (Batch 5)
└── README.md (this file)
```

## Extraction Pipeline

The complete extraction pipeline processes Armenian corpus data through 8 sequential tools (batches 2-6):

### 1. Export Core Contracts (Batch 2)
```bash
python -m armenian_corpus_core.extraction.export_core_contracts_jsonl \
  --db-path 08-data/armenian_cards.db \
  --lexicon-out 08-data/export_lexicon_entries.jsonl \
  --documents-out 08-data/export_document_records.jsonl
```

**Inputs**: Lousardzag SQLite DB (anki_cards + sentences tables)  
**Outputs**: `LexiconEntry` + `DocumentRecord` JSONL files

---

### 2. Validate Contract Alignment (Batch 3)
```bash
python -m armenian_corpus_core.extraction.validate_contract_alignment \
  --lexicon-jsonl 08-data/export_lexicon_entries.jsonl \
  --documents-jsonl 08-data/export_document_records.jsonl \
  --wa-exports-dir /path/to/WesternArmenianLLM/migration_exports
```

**Purpose**: Cross-project validation (lousardzag vs. WesternArmenianLLM)  
**Checks**: 7 validation rules (schema, dialect tags, field presence)  
**Output**: JSON validation report

---

### 3. Ingest WA Fingerprints (Batch 4)
```bash
python -m armenian_corpus_core.extraction.ingest_wa_fingerprints_to_contracts \
  --fingerprint-csv corpus_fingerprints.csv \
  --output-jsonl 08-data/wa_fingerprint_document_records.jsonl
```

**Input**: WesternArmenianLLM CSV fingerprints (32K+ records)  
**Output**: `DocumentRecord` JSONL with preserved source hashing  
**Dialect**: Handles WA/EA/Mixed mapping

---

### 4. Merge Document Records (Batch 5 - Basic)
```bash
python -m armenian_corpus_core.extraction.merge_document_records \
  --local-jsonl 08-data/export_document_records.jsonl \
  --wa-jsonl 08-data/wa_fingerprint_document_records.jsonl \
  --output-jsonl 08-data/unified_document_records.jsonl
```

**Algorithm**: 
- Primary key: `content_hash` (NFKC-normalized SHA256)
- Fallback key: `document_id`
- Conflict resolution: Prefer records with non-empty text, then longer text

**Input**: 42,627 records (32,627 local + 10,000 WA)  
**Output**: 26,239 unified records (38.5% dedup efficiency)

---

### 5. Merge with Profiles (Batch 6 - Advanced)
```bash
# App-ready profile (prioritize local content)
python -m armenian_corpus_core.extraction.merge_document_records_with_profiles \
  --profile app-ready \
  --local-jsonl 08-data/export_document_records.jsonl \
  --wa-jsonl 08-data/wa_fingerprint_document_records.jsonl \
  --output-jsonl 08-data/unified_document_records_app-ready.jsonl

# Corpus-ready profile (prioritize metadata richness)
python -m armenian_corpus_core.extraction.merge_document_records_with_profiles \
  --profile corpus-ready \
  --output-jsonl 08-data/unified_document_records_corpus-ready.jsonl
```

**Profiles**:
- **app-ready**: Local > Text > Length > Metadata (production-ready datasets)
- **corpus-ready**: Metadata > Text > Length > Local (research corpus)

---

### 6. Extract Fingerprint Index (Batch 6)
```bash
python -m armenian_corpus_core.extraction.extract_fingerprint_index \
  --unified-jsonl 08-data/unified_document_records.jsonl \
  --content-only-jsonl 08-data/unified_document_records_content_only.jsonl \
  --fingerprint-index-jsonl 08-data/unified_document_records_fingerprint_index.jsonl
```

**Purpose**: Separate fingerprint-only (empty text) from content-bearing records  
**Output**: 
- Content-only: 16,240 records (61.9%)
- Fingerprint-only: 9,999 records (38.1%)

**Use case**: Training safety—ML pipelines can explicitly choose content vs. metadata mode

---

### 7. Materialize Dialect Views (Batch 6)
```bash
python -m armenian_corpus_core.extraction.materialize_dialect_views \
  --unified-jsonl 08-data/unified_document_records.jsonl \
  --wa-jsonl 08-data/materialized_wa_documents.jsonl \
  --ea-jsonl 08-data/materialized_ea_documents.jsonl \
  --mixed-jsonl 08-data/materialized_mixed_documents.jsonl
```

**Output**: Dialect-specific views
- WA (Western Armenian): 26,239 records
- EA (Eastern Armenian): 0 records (placeholder for future)
- MIXED: 0 records (placeholder for future)

---

### 8. Summarize Pipeline (Batch 5)
```bash
python -m armenian_corpus_core.extraction.summarize_unified_documents \
  --unified-jsonl 08-data/unified_document_records.jsonl \
  --output-json 08-data/unified_document_records_summary.json
```

**Output**: Dataset statistics and distribution by source family, dialect

---

## Full Pipeline Execution

### Local (Orchestrated)
```bash
# Run entire pipeline
cd /path/to/lousardzag
python -m armenian_corpus_core.extraction.run_extraction_pipeline --project lousardzag

# Dry-run (show what would execute)
python -m armenian_corpus_core.extraction.run_extraction_pipeline --project lousardzag --dry-run

# Skip specific tools
python -m armenian_corpus_core.extraction.run_extraction_pipeline \
  --project lousardzag \
  --skip validate_contract_alignment \
  --skip ingest_wa_fingerprints_to_contracts
```

### CI/CD (GitHub Actions)
This repository currently ships extraction tooling only and does not yet include
its own GitHub Actions workflow. Pipeline automation is currently expected to run
from an integration repository (for example lousardzag) where source databases
and migration exports are available.

Recommended automation setup:
- Run `python -m armenian_corpus_core.extraction.run_extraction_pipeline --project <path>` from the integration repo context.
- Persist generated `08-data` outputs and `pipeline_execution_report.json` as build artifacts.
- Add schedule/dispatch triggers in the integration repo workflow where source data is accessible.

---

## Core Contracts

### DocumentRecord
```python
@dataclass(frozen=True)
class DocumentRecord:
    document_id: str              # Unique identifier
    source_family: str            # lousardzag_sentences, wikipedia, etc.
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
    dialect_tag: DialectTag       # Dialect
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
from armenian_corpus_core.extraction.registry import (
    get_registry,
    get_tool_spec,
    list_all_tools,
    get_pipeline_execution_order,
)

# Get all tools
tools = list_all_tools()

# Get specific tool metadata
spec = get_tool_spec("merge_document_records")
print(spec.description)  # "Merge and deduplicate DocumentRecord JSONL files (basic)"
print(spec.inputs)       # ["export_document_records.jsonl", "wa_fingerprint_document_records.jsonl"]
print(spec.outputs)      # ["unified_document_records.jsonl"]

# Get execution order
pipeline = get_pipeline_execution_order()
for tool in pipeline:
    print(f"{tool.batch}: {tool.name}")
```

---

## Integration

### Lousardzag Integration

Update `lousardzag` to use the central package:

```python
# Preferred (central package contracts)
from armenian_corpus_core.core_contracts import DocumentRecord, LexiconEntry

# Fallback (if central package not installed)
try:
  from armenian_corpus_core.core_contracts import DocumentRecord, LexiconEntry
except ImportError:
    from lousardzag.core_contracts import DocumentRecord, LexiconEntry
```

### WesternArmenianLLM Integration

Import tools from central registry:

```python
from armenian_corpus_core.extraction.registry import get_tool_spec

tool_spec = get_tool_spec("ingest_wa_fingerprints_to_contracts")
print(f"Using tool: {tool_spec.description}")
print(f"Inputs: {tool_spec.inputs}")
print(f"Outputs: {tool_spec.outputs}")
```

---

## Development

### Installation (Editable)
```bash
cd /path/to/armenian-corpus-core
pip install -e .
```

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
- ⏳ Move core contracts to central package

### Phase 2: Adapter Wrappers
- Create import shims in lousardzag and WesternArmenianLLM
- Route through central package with fallback to local
- Update CI/CD to use central package

### Phase 3: Enhancement
- Implement `hybrid` profile for statistical conflict resolution
- Add incremental merge (only re-process changed records)
- Create format converters (parquet, CSV variants)
- Add comprehensive test suite

### Phase 4: Distribution
- Publish to PyPI / internal package repo
- Create documentation site
- Add performance benchmarks

---

## Status & Support

**Current Status**: 🟡 Alpha (Batch 7)  
**Stability**: Extraction pipeline validated with 42K+ real records  
**Breaking Changes**: Possible in alpha releases  
**Support**: Issues and PRs welcome in lousardzag repository

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

**Extraction Tools**:
- `armenian_corpus_core/extraction/__init__.py` — Module exports
- `armenian_corpus_core/extraction/registry.py` — Tool registry and discovery
- `armenian_corpus_core/extraction/run_extraction_pipeline.py` — Orchestration CLI
- `armenian_corpus_core/extraction/export_core_contracts_jsonl.py` (Batch 2)
- `armenian_corpus_core/extraction/validate_contract_alignment.py` (Batch 3)
- `armenian_corpus_core/extraction/ingest_wa_fingerprints_to_contracts.py` (Batch 4)
- `armenian_corpus_core/extraction/merge_document_records.py` (Batch 5)
- `armenian_corpus_core/extraction/merge_document_records_with_profiles.py` (Batch 6)
- `armenian_corpus_core/extraction/extract_fingerprint_index.py` (Batch 6)
- `armenian_corpus_core/extraction/materialize_dialect_views.py` (Batch 6)
- `armenian_corpus_core/extraction/summarize_unified_documents.py` (Batch 5)

---

## References

- **Lousardzag**: https://github.com/lousardzag/lousardzag
- **WesternArmenianLLM**: (internal repo)
- **Batch Documentation**: See BATCH_*.md files in lousardzag
- **Contracts**: Core data types defined in lousardzag via `02-src/lousardzag/core_contracts/`

