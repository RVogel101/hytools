# Import Conventions: Flat Packages Only

**`armenian_corpus_core` does not exist.** It was decommissioned and removed. This project uses **flat packages** only. **No data or processes should be sourced from WesternArmenianLLM.**

## Current Package Structure (Use These)

| Package | Module examples |
|---------|-----------------|
| `cleaning` | `cleaning.language_filter`, `cleaning.armenian_tokenizer` |
| `scraping` | `scraping.wikipedia_wa`, `scraping.loc`, `scraping.metadata_tagger` |
| `augmentation` | `augmentation.batch_worker`, `augmentation.metrics_pipeline` |
| `linguistics` | `linguistics.metrics`, `linguistics.metrics.dialect_distance`, `linguistics.metrics.text_metrics` |
| `ocr` | `ocr.pipeline`, `ocr.preprocessor`, `ocr.postprocessor` |
| `integrations` | `integrations.database.mongodb_client` |
| `research` (moved) | `ingestion.discovery.book_inventory_runner`, `ingestion.research_runner`; discovery: `ingestion.discovery.*`, enrichment: `ingestion.enrichment.biography_enrichment`, aggregation: `ingestion.aggregation.coverage_analysis`, `ingestion.aggregation.timeline_generation` |
| `core_contracts` | `core_contracts.types` |

## Do Not Use (Removed)

- `armenian_corpus_core.*` — package does not exist; imports will fail
- `src.augmentation.*`, `src.database.*` — use `augmentation.*`, `integrations.database.*` instead

## Running the Project

From project root with `pip install -e .` or PYTHONPATH including project root:

```bash
python -m scraping.runner run
python -m augmentation.runner run
python -m augmentation.runner metrics
```
