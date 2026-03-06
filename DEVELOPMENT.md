# Local Development Installation Guide

This guide explains how to install `armenian-corpus-core` locally for development and integration testing.

## Quick Start (5 minutes)

### Option 1: Editable Install (Recommended for Development)

```bash
# Navigate to the central package directory
cd C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Verify installation
python -c "from armenian_corpus_core.extraction.registry import get_registry; print('✓ Successfully imported')"
```

### Option 2: Manual Path Addition (For Testing Without Install)

If you prefer not to install globally, add the central package to your Python path:

```python
# In any script that needs the central package
import sys
from pathlib import Path

# Add central package to path
central_pkg = Path.home() / "OneDrive" / "Documents" / "anki" / "armenian-corpus-core"
if str(central_pkg) not in sys.path:
    sys.path.insert(0, str(central_pkg))

# Now imports work
from armenian_corpus_core.extraction.registry import get_registry
```

---

## Detailed Installation

### Prerequisites

- Python 3.10+
- pip (package installer)
- setuptools (usually included)

**Check your versions:**
```bash
python --version  # Should be 3.10 or higher
pip --version
```

### Step 1: Editable Install

An "editable install" (also called development install) allows you to modify the package code and see changes immediately without reinstalling.

```bash
cd C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core
pip install -e .
```

**What this does:**
- Creates a link from your Python site-packages to the local `armenian-corpus-core` directory
- Allows importing `armenian_corpus_core` from anywhere
- Changes to source files are picked up immediately

**Editable install with dev dependencies:**
```bash
pip install -e ".[dev]"
```

This also installs testing and code quality tools (pytest, black, isort, mypy).

### Step 2: Verify Installation

```bash
# Test basic import
python -c "import armenian_corpus_core; print(f'Version: {armenian_corpus_core.__version__}')"

# Test registry import
python -c "from armenian_corpus_core.extraction.registry import get_registry; registry = get_registry(); print(f'Tools: {len(registry.list_tools())}')"

# Test adapter import
python -c "from lousardzag.core_adapters import get_extraction_registry; print('✓ Adapter imports work')"
```

---

## Using the Installed Package

### From Lousardzag

After installation, lousardzag can transparently use the central package:

```python
# In lousardzag code
from lousardzag.core_adapters import get_extraction_registry

registry = get_extraction_registry()
if registry:
    print("Using central package registry")
    tools = registry.list_available_tools()
else:
    print("Central package not available, using local fallback")
```

**Environment Control:**
```bash
# Enable central package usage
set LOUSARDZAG_USE_CENTRAL_PACKAGE=1
python script.py

# Or disable (default safe mode)
set LOUSARDZAG_USE_CENTRAL_PACKAGE=0
python script.py
```

### Running the Orchestration CLI

After installation, the pipeline runner is available:

```bash
cd C:\Users\litni\OneDrive\Documents\anki\lousardzag

# Central package install provides the runner
python -m armenian_corpus_core.extraction.run_extraction_pipeline --project lousardzag

# Or run directly
python ../../armenian-corpus-core/extraction/run_extraction_pipeline.py --project lousardzag
```

---

## Project Structure After Installation

```
C:\Users\litni\OneDrive\Documents\anki\
├── lousardzag/
│   ├── 02-src/lousardzag/
│   │   ├── core_adapters.py          # Adapter for central package
│   │   └── (other lousardzag modules)
│   ├── 07-tools/extraction/          # Local extraction tools
│   │   ├── export_core_contracts_jsonl.py
│   │   ├── merge_document_records.py
│   │   └── (other tools)
│   └── (rest of lousardzag)
│
└── armenian-corpus-core/             # NEWLY INSTALLED
    ├── armenian_corpus_core/
    │   ├── __init__.py
    │   ├── extraction/
    │   │   ├── registry.py
    │   │   └── run_extraction_pipeline.py
    │   └── (other modules)
    ├── setup.py
    ├── pyproject.toml
    └── README.md
```

**Python Site-Packages Link** (created by `pip install -e .`):
```
C:\Python312\Lib\site-packages\armenian-corpus-core.egg-link
    → C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core
```

This link allows `import armenian_corpus_core` from anywhere.

---

## Development Workflow

### Making Changes

1. **Modify files** in `armenian-corpus-core/extraction/`
2. **No reinstall needed**—editable install detects changes automatically
3. **Test immediately**:
   ```bash
   python -c "from armenian_corpus_core.extraction.registry import get_registry; ..."
   ```

### Running Tests

```bash
cd C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core

# Run all tests
pytest

# Run specific test file
pytest tests/test_registry.py

# Run with coverage
pytest --cov=armenian_corpus_core
```

### Code Quality

```bash
# Format code
black armenian_corpus_core/

# Sort imports
isort armenian_corpus_core/

# Type check
mypy armenian_corpus_core/

# Lint
flake8 armenian_corpus_core/
```

---

## Uninstalling / Reinstalling

### Uninstall
```bash
pip uninstall armenian-corpus-core
```

This removes the egg-link but doesn't delete the source files.

### Reinstall
```bash
cd C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core
pip install -e .
```

---

## Troubleshooting

### Import Error: No module named 'armenian_corpus_core'

**Solution 1**: Verify installation
```bash
pip show armenian-corpus-core
# Should show Location: ... with egg-link info
```

**Solution 2**: Check Python path
```python
import sys
print(sys.path)
# Should include central package directory
```

**Solution 3**: Reinstall
```bash
pip uninstall armenian-corpus-core
pip install -e C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core
```

### ImportError in lousardzag despite installation

Check the adapter fallback:
```python
from lousardzag.core_adapters import get_extraction_registry

registry = get_extraction_registry()
print(registry)  # Should not be None if LOUSARDZAG_USE_CENTRAL_PACKAGE=1
```

If None, either:
1. Environment variable not set: `set LOUSARDZAG_USE_CENTRAL_PACKAGE=1`
2. Central package not installed: `pip install -e path/to/armenian-corpus-core`

### Module Conflicts

If you have local clones of the central package in multiple places:
```bash
# Find all installations
pip show armenian-corpus-core -v
# Check the egg-link points to the right directory
```

---

## For WesternArmenianLLM Project

Follow the same installation steps. After `pip install -e .`, the project can import:

```python
# In WesternArmenianLLM code
from armenian_corpus_core.extraction.registry import get_tool_spec

tool = get_tool_spec("ingest_wa_fingerprints_to_contracts")
print(f"Tool: {tool.description}")
print(f"Inputs: {tool.inputs}")
print(f"Outputs: {tool.outputs}")
```

---

## Integration with Git Workflow

### Local Installation (Development)

```bash
# Clone both repos
git clone <lousardzag-repo>
git clone <wa-llm-repo>
cd <central-package-dir>

# Install in editable mode
pip install -e .

# Now both projects can import from it
cd ../lousardzag
python -c "from armenian_corpus_core.extraction.registry import get_registry; print('✓')"
```

### CI/CD Behavior

GitHub Actions will:
1. Check out the lousardzag repo
2. See the extraction tools in `07-tools/extraction/`
3. Run them with the orchestration CLI
4. Pass environment variable `LOUSARDZAG_USE_CENTRAL_PACKAGE=1` if installed
5. Fall back to local tools if central package not available

---

## Next Steps

1. ✅ **Install**: `pip install -e C:\Users\litni\OneDrive\Documents\anki\armenian-corpus-core`
2. ✅ **Verify**: `python -c "from armenian_corpus_core.extraction.registry import get_registry; print(get_registry().list_tools())"`
3. ✅ **Configure Lousardzag**: Set `LOUSARDZAG_USE_CENTRAL_PACKAGE=1` environment variable
4. ✅ **Test Integration**: Run the orchestration CLI locally
5. ✅ **Document**: This guide and the README.md provide complete documentation

---

## References

- **Python Packaging**: https://packaging.python.org/
- **Editable Installs**: https://pip.pypa.io/en/latest/topics/local-project-installs/
- **setuptools**: https://setuptools.pypa.io/
