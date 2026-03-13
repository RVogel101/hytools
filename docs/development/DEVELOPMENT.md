# Development Guide

## Quick Start

```bash
cd C:\Users\litni\armenian_projects\armenian-corpus-core

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -m scraping.runner list
```

## Prerequisites

- Python 3.10+
- MongoDB running locally on `mongodb://localhost:27017/`
- pip / setuptools

## Running the Pipeline

```bash
# Run the full pipeline (scraping + extraction + post-processing)
python -m scraping.runner run

# Run only scraping stages
python -m scraping.runner run --group scraping

# Run only extraction stages
python -m scraping.runner run --group extraction

# Run only post-processing stages
python -m scraping.runner run --group postprocessing

# Skip specific stages
python -m scraping.runner run --skip hathitrust nayiri

# Run specific stages only
python -m scraping.runner run --only wikipedia_wa wikisource culturax

# Run in background
python -m scraping.runner run --background

# Check status
python -m scraping.runner status

# List all registered stages
python -m scraping.runner list
```

## Project Structure

```
armenian-corpus-core/
├── scraping/                  # All data collection and extraction
│   ├── runner.py              # Unified pipeline orchestrator
│   ├── registry.py            # Stage metadata catalog
│   ├── wikipedia_wa.py        # Western Armenian Wikipedia scraper
│   ├── wikipedia_ea.py        # Eastern Armenian Wikipedia scraper
│   ├── wikisource.py          # Wikisource scraper (dialect-classified)
│   ├── archive_org.py         # Internet Archive scraper
│   ├── hathitrust.py          # HathiTrust Digital Library scraper
│   ├── loc.py                 # Library of Congress scraper
│   ├── newspaper.py           # Diaspora newspaper scraper (Selenium)
│   ├── ea_news.py             # Eastern Armenian news agencies
│   ├── rss_news.py            # RSS/Atom feed scraper (full-text)
│   ├── culturax.py            # CulturaX HuggingFace dataset
│   ├── english_sources.py     # English-language academic sources
│   ├── nayiri.py              # Nayiri dictionary scraper (Selenium)
│   ├── mss_nkr.py             # Matenadaran NKR archive
│   ├── import_anki_sqlite.py   # Anki SQLite -> MongoDB
│   ├── _wa_filter.py          # Western Armenian dialect classifier
│   ├── _mongodb_helper.py     # Shared MongoDB utilities
│   └── (other extraction/post-processing modules)
├── core_contracts/            # Canonical data types
│   ├── types.py               # DocumentRecord, LexiconEntry, etc.
│   └── hashing.py             # Content normalization and hashing
├── integrations/              # External system adapters
│   ├── anki/                  # AnkiConnect client
│   └── database/              # MongoDB client, SQLite adapters
├── linguistics/               # Language analysis tools
│   ├── dialect_classifier.py  # WA/EA dialect detection
│   └── phonetics.py           # Armenian phonetics/IPA
├── cleaning/                  # Text normalization and filtering
├── tests/                     # Test suite
├── pyproject.toml
└── README.md
```

## Running Tests

```bash
pytest tests/
pytest tests/test_mappers.py -v
pytest --cov=scraping
```

## Code Quality

```bash
black scraping/ core_contracts/ integrations/ linguistics/
isort scraping/ core_contracts/ integrations/ linguistics/
mypy scraping/
```

---

## Troubleshooting

### Import Error: No module named ...

Verify installation:
```bash
pip show armenian-corpus-core
```

Reinstall:
```bash
pip install -e .
```

### MongoDB Connection Error

Ensure MongoDB is running:
```bash
mongosh --eval "db.adminCommand('ping')"
```

---

## References

- **Python Packaging**: https://packaging.python.org/
- **Editable Installs**: https://pip.pypa.io/en/latest/topics/local-project-installs/
- **MongoDB Python Driver**: https://pymongo.readthedocs.io/
