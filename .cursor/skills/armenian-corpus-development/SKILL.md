---
name: armenian-corpus-development
description: Run and develop the armenian-corpus-core pipeline (scraping, extraction, tests, code quality). Use when running the pipeline, writing tests, fixing import or MongoDB errors, or understanding package layout and import conventions.
---

# Armenian Corpus Core — Development

## Quick start

From project root (`armenian-corpus-core`):

```bash
pip install -e ".[dev]"
python -m ingestion.runner list
```

Prerequisites: Python 3.10+, MongoDB on `mongodb://localhost:27017/`.

---

## Running the pipeline

```bash
# Full pipeline (acquisition + extraction + post-processing)
python -m ingestion.runner run

# By group
python -m ingestion.runner run --group scraping
python -m ingestion.runner run --group extraction
python -m ingestion.runner run --group postprocessing

# Filter stages
python -m ingestion.runner run --skip hathitrust nayiri
python -m ingestion.runner run --only wikipedia wikisource culturax

# Background
python -m ingestion.runner run --background
python -m ingestion.runner status
```

---

## Package structure (flat only)

**Do not use** `armenian_corpus_core.*` — that package was removed. Use **flat packages**:

| Package | Examples |
|---------|----------|
| `ingestion` | `ingestion.runner`, `ingestion.acquisition.loc`, `ingestion.enrichment.metadata_tagger` |
| `cleaning` | `cleaning.language_filter`, `cleaning.armenian_tokenizer` |
| `augmentation` | `augmentation.batch_worker`, `augmentation.runner` |
| `linguistics` | `linguistics.metrics.dialect_distance`, `linguistics.metrics.text_metrics` |
| `integrations` | `integrations.database.mongodb_client` |
| `core_contracts` | `core_contracts.types` |
| `ocr` | `ocr.pipeline`, `ocr.preprocessor` |
| `ingestion` (research) | `ingestion.discovery.book_inventory_runner`, `ingestion.research_runner`; discovery: `ingestion.discovery.*`, enrichment: `ingestion.enrichment.biography_enrichment`, aggregation: `ingestion.aggregation.coverage_analysis`, `ingestion.aggregation.timeline_generation` |

Run from project root with `pip install -e .` or PYTHONPATH including project root:

```bash
python -m ingestion.runner run
python -m augmentation.runner run
python -m augmentation.runner metrics
```

---

## Tests and code quality

```bash
pytest tests/
pytest tests/test_mappers.py -v
pytest --cov=scraping

black scraping/ core_contracts/ integrations/ linguistics/
isort scraping/ core_contracts/ integrations/ linguistics/
mypy scraping/
```

---

## Troubleshooting

**Import error (no module named ...)**  
- Verify: `pip show armenian-corpus-core`  
- Reinstall: `pip install -e .`

**MongoDB connection error**  
- Ensure MongoDB is running: `mongosh --eval "db.adminCommand('ping')"`

---

## References

- Full dev guide: `docs/development/DEVELOPMENT.md`
- Package layout and scraper-adding steps: `docs/STRUCTURE.md`
- Import conventions: `docs/IMPORT_REDIRECTS.md`
