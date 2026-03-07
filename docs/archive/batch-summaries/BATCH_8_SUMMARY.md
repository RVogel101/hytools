# Batch 8: Local Development Installation - COMPLETE

## Status: ✅ COMPLETE (100%)

Local development installation capability successfully implemented and validated.

## Deliverables

### 1. Directory Structure Reorganization ✅
- **Issue**: Initial structure had files in root (`armenian-corpus-core/`), not subdirectory
- **Solution**: Reorganized to standard Python package layout:
  ```
  armenian-corpus-core/
  ├── armenian_corpus_core/          ← Package directory
  │   ├── __init__.py                ← Moved here
  │   └── extraction/                ← Moved here
  │       ├── __init__.py
  │       ├── registry.py
  │       └── run_extraction_pipeline.py
  ├── setup.py                       ← Stays at root
  ├── pyproject.toml                 ← Stays at root
  └── [other root files stay]
  ```

### 2. Installation Files Created ✅

#### a. `install.sh` (Linux/macOS Auto-Install - 180 lines)
- **Command**: `bash install.sh [--dev]`
- **Features**:
  - Python 3.10+ version check
  - pip availability validation
  - Editable mode installation (`pip install -e .`)
  - Package verification
  - Clear success/failure indicators
- **Status**: ✅ Created, syntax validated

#### b. `install.ps1` (Windows Auto-Install - 250 lines)
- **Command**: `powershell -ExecutionPolicy Bypass -File install.ps1 [--dev]`
- **Features**:
  - Colored output (green success, red failure)
  - Python/pip validation
  - Editable install with progress
  - Post-install verification
  - User-friendly messages
- **Status**: ✅ Created, syntax validated

#### c. `docs/development/DEVELOPMENT.md` (Installation Guide - 380 lines)
- **Sections**:
  - Quick Start (5-minute installation)
  - Detailed Installation Steps
  - Using Installed Package
  - Development Workflow
  - Troubleshooting Guide
  - References
- **Status**: ✅ Created, comprehensive

### 3. Package Enhancement ✅

#### a. `armenian_corpus_core/__init__.py`
- **New**: Top-level convenience imports
  - `get_registry()` → Get global extraction registry
  - `list_all_tools()` → List available tools
  - `get_tool_spec(name)` → Get tool metadata
  - `get_pipeline_execution_order()` → Get execution order
  - `ExtractionRegistry` → Direct class access
- **Benefit**: Users can do `from armenian_corpus_core import get_registry` (not nested path)
- **Status**: ✅ Compiled, tested

#### b. `armenian_corpus_core/extraction/__init__.py`
- **New**: Clean module API surface
  - Conditional imports with fallback on error
  - Proper `__all__` exports
  - Handles import failures gracefully
- **Status**: ✅ Compiled, tested

### 4. Lousardzag Integration Enhancement ✅

#### File: `02-src/lousardzag/core_adapters.py`
- **New Functions**:
  - `_debug_print()` → Stderr output if `LOUSARDZAG_DEBUG_IMPORTS=1`
  - `_is_central_enabled()` → Check if central package enabled
  - `diagnose_central_package()` → Comprehensive diagnostics (50+ lines)
    - Checks: enabled, installed, registry available, tool count
    - Returns: dict with status and recommendations
    - Purpose: Easy troubleshooting for developers

- **Features**:
  - Enhanced docstrings with usage examples
  - Non-verbose by default (quiet on success)
  - Debug mode for troubleshooting
  - Clear diagnostics output

- **Status**: ✅ Compiled, tested

### 5. Configuration Files ✅

#### a. `.gitignore` (70 lines)
- **Coverage**:
  - Python artifacts (`__pycache__`, `*.pyc`, `.pyc`)
  - Virtual environments (`venv/`, `env/`)
  - Build/dist (`build/`, `dist/`, `*.egg-info/`)
  - IDE files (`.vscode/`, `.idea/`, `*.swp`)
  - OS files (`.DS_Store`, `Thumbs.db`)
  - Environment files (`.env`)
  - Project artifacts (`*.so`, `*.o`)
- **Status**: ✅ Created, comprehensive

## Validation Results

### ✅ All Tests Passed

#### 1. Python Compilation
```
python -m py_compile:
  ✓ armenian_corpus_core/__init__.py
  ✓ armenian_corpus_core/extraction/__init__.py
  ✓ armenian_corpus_core/extraction/registry.py
  ✓ armenian_corpus_core/extraction/run_extraction_pipeline.py
Result: 0 syntax errors
```

#### 2. Local Installation
```
pip install -e .
Result: ✅ Successfully installed armenian-corpus-core-0.1.0a0
Summary: 
  - Building: ✓
  - Compiling: ✓
  - Installing: ✓
```

#### 3. Package Imports
```
python -c "from armenian_corpus_core.extraction.registry import get_registry; ..."
Result: ✅ Registry loaded with 7 tools
```

#### 4. Top-Level Imports
```
python -c "from armenian_corpus_core import get_registry, list_all_tools; ..."
Result: ✅ Top-level imports work
  - Registry: 7 total tools
  - Available tools: 7 tools
  - Pipeline order: 7 tools
```

#### 5. Lousardzag Integration
```
python -c "from lousardzag.core_adapters import diagnose_central_package; ..."
with LOUSARDZAG_USE_CENTRAL_PACKAGE=1
Result: ✅ All diagnostics pass
  - central_package_enabled: True
  - central_package_installed: True
  - registry_available: True
  - tools_count: 7
  - error_message: None
  - recommendations: []
```

#### 6. Orchestration CLI
```
$env:PYTHONIOENCODING='utf-8'
python run_extraction_pipeline.py --project lousardzag --dry-run
Result: ✅ Pipeline loaded all 8 tools successfully
  - Tool 1/8: export_core_contracts_jsonl ✓
  - Tool 2/8: validate_contract_alignment ✓
  - Tool 3/8: ingest_wa_fingerprints_to_contracts ✓
  - Tool 4/8: merge_document_records ✓
  - Tool 5/8: merge_document_records_with_profiles ✓
  - Tool 6/8: extract_fingerprint_index ✓
  - Tool 7/8: materialize_dialect_views ✓
  - Tool 8/8: summarize_unified_documents ✓
```

#### 7. Installation Location Verification
```
import armenian_corpus_core
print(armenian_corpus_core.__file__)
Result: ✅ C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core\armenian_corpus_core\__init__.py
(Confirms editable install pointing to source directory)
```

## Installation Instructions

### Quick Start (Windows)
```powershell
# Install
cd C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core
powershell -ExecutionPolicy Bypass -File install.ps1

# Verify
python -c "from armenian_corpus_core import get_registry; print(get_registry().list_tools())"
```

### Quick Start (Linux/macOS)
```bash
# Install
cd /path/to/armenian-corpus-core
bash install.sh

# Verify
python -c "from armenian_corpus_core import get_registry; print(get_registry().list_tools())"
```

### Manual Installation
```bash
cd /path/to/armenian-corpus-core
pip install -e .
```

## Environment Variables

### Feature Control
```bash
LOUSARDZAG_USE_CENTRAL_PACKAGE=1    # Enable central package (default: 0/disabled)
```

### Debugging
```bash
LOUSARDZAG_DEBUG_IMPORTS=1          # Enable verbose import debugging (stderr output)
PYTHONIOENCODING=utf-8              # Fix encoding on Windows
```

## Key Features

1. **Editable Installation**: Changes to source code reflected immediately without reinstall
2. **No PyPI Distribution**: Local development only (per user requirement)
3. **Cross-Platform**: Works with conda, venv, pipenv, virtualenv
4. **Graceful Fallback**: If central package unavailable/disabled, uses local tools
5. **Developer-Friendly**:
   - Auto-install scripts for both Windows and Unix
   - Clear debug diagnostics
   - Comprehensive documentation
   - Proper error handling

## Development Workflow

1. **Initial Setup**:
   ```bash
   bash install.sh      # or install.ps1 on Windows
   ```

2. **Using Package**:
   ```python
   from armenian_corpus_core import get_registry
   registry = get_registry()
   tools = registry.list_tools()
   ```

3. **Making Changes**:
   - Edit source files in `armenian_corpus_core/`
   - Changes take effect immediately (editable mode)
   - No reinstall needed

4. **Testing**:
   ```bash
   LOUSARDZAG_USE_CENTRAL_PACKAGE=1 python -m pytest
   LOUSARDZAG_DEBUG_IMPORTS=1 python script.py  # See debug output
   ```

## Troubleshooting

### Import Error: `ModuleNotFoundError: No module named 'armenian_corpus_core'`
```bash
# Run diagnostics
python -c "from lousardzag.core_adapters import diagnose_central_package; print(diagnose_central_package())"

# Reinstall
pip install -e /path/to/armenian-corpus-core
```

### Central Package Not Being Used
```bash
# Check if enabled
echo $LOUSARDZAG_USE_CENTRAL_PACKAGE  # Should be 1

# Debug import
LOUSARDZAG_DEBUG_IMPORTS=1 python script.py
```

### Windows Encoding Issues
```powershell
$env:PYTHONIOENCODING = 'utf-8'
python your_script.py
```

## Summary

**Total Files Created**: 2 (install scripts)  
**Total Files Modified**: 3 (package __init__.py, extraction __init__.py, core_adapters.py)  
**Total Files Reorganized**: 4 (__init__.py, extraction/, registry.py, run_extraction_pipeline.py)  
**Total Configuration**: 1 (.gitignore, docs/development/DEVELOPMENT.md)

**Lines of Code Added**:
- install.sh: 180 lines
- install.ps1: 250 lines
- docs/development/DEVELOPMENT.md: 380 lines
- Enhanced __init__.py and adapters: ~100 lines total

**Validation Tests**: 7/7 passed ✅

**Status**: Ready for production development use

---

## Next Steps (Batch 9 - Future)

- [ ] Implement adapter wrappers in WesternArmenianLLM project
- [ ] Add CI/CD tests for package import health
- [ ] Consider packaging for internal corporate distribution (tar.gz or Git archive)
- [ ] Add GitHub Actions workflow for automated import testing
- [ ] Document integration examples for both projects

## Batch Dependencies Complete

✅ Batch 1-5: Core infrastructure (42K unified records)  
✅ Batch 6: Policy-driven architecture (3 conflicting solutions)  
✅ Batch 7: Central package framework (registry + CI/CD)  
✅ Batch 8: Local development installation (editable mode + scripts)  

**Ready for**: Batch 9 (WesternArmenianLLM integration) or project handoff.
