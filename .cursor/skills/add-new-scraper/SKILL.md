---
name: add-new-scraper
description: Add a new scraper or data-acquisition stage to armenian-corpus-core. Use when adding a new data source, implementing a new scraper module, or registering a stage in the ingestion runner.
---

# Adding a New Acquisition Stage (Ingestion)

## Steps

1. **Pick the subpackage** under `ingestion/` (Option B layout):
   - **`ingestion/acquisition/`** — External sources → MongoDB:
     - Wikimedia: `wiki.py` (Wikipedia WA/EA + Wikisource)
     - Digital libraries: `archive_org.py`, `hathitrust.py`, `gallica.py`, `loc.py`, `dpla.py`
     - News: `news.py` (diaspora newspapers + EA agencies + RSS)
     - Datasets: `culturax.py`, `english_sources.py`
     - Reference: `nayiri.py`, `gomidas.py`, `mechitarist.py`, `agbu.py`, `mss_nkr.py`, `ocr_ingest.py`
   - **`ingestion/discovery/`** — Catalog search: `worldcat_searcher.py`
   - **`ingestion/extraction/`** — Other stores → MongoDB: `import_anki_sqlite.py`
   - **`ingestion/enrichment/`** — MongoDB backfill: `metadata_tagger.py`, `materialize_dialect_views.py`
   - **`ingestion/aggregation/`** — Derived collections: `frequency_aggregator.py`, `word_frequency_facets.py`, `summarize_unified_documents.py`
   - **`ingestion/validation/`** — Integrity: `validate_contract_alignment.py`, `export_corpus_overlap_fingerprints.py`

2. **Implement the entry-point** in the new module:
   - Prefer **`run(config: dict) -> None`** for pipeline stages. Use **`main() -> int`** for CLI and have it load config (e.g. from `--config`) and call `run(config)`.
   - Use `open_mongodb_client(config)` and `insert_or_skip()` from **`ingestion._shared.helpers`**.

3. **Register in the runner**: In **`ingestion/runner.py`**, add the stage to `_build_stages()` with the correct module path (e.g. `ingestion.acquisition.new_source`). It will appear in `python -m ingestion.runner list` and work with `--only` / `--skip`.

4. **If MongoDB-capable**: Set `supports_mongodb=True` on the `Stage` in `_build_stages()`.

---

## Scraper patterns (from existing code)

- **Catalog-based tracking**: Build/maintain a catalog (e.g. in MongoDB `catalogs` collection) with item metadata and download status.
- **Resume**: Skip already-downloaded items using the catalog.
- **WA filtering**: Optionally apply Western Armenian classifier (`try_wa_filter` from `ingestion._shared.helpers`) when config says so.
- **Rate limiting**: Use a configurable delay (e.g. `_REQUEST_DELAY`) between requests.
- **Error handling**: Retry with exponential backoff; log failures (e.g. to `data/logs/<source>_errors.jsonl`).

---

## Config shape

Config is under **`ingestion`** (or **`scraping`** for backward compatibility). In `config/settings.yaml`:

```yaml
ingestion:
  <source_name>:
    enabled: true
    queries:
      - "search term 1"
    max_results: 250
    apply_wa_filter: true
```

For API keys (e.g. DPLA): use `config["ingestion"]["<source>"]["api_key"]` or env (e.g. `DPLA_API_KEY`).

---

## Storage

- **MongoDB-only**: Write documents to `documents`, catalogs to `catalogs`. No local JSON/txt persistence for corpus data; only logs (e.g. `data/logs/`) as needed.
- Align `source` identifiers with **`ingestion/enrichment/metadata_tagger.py`** SOURCE_METADATA so metadata tagging can map sources to regions/dialects.

---

## References

- Package layout: **`docs/concept_guides/STRUCTURE.md`**
- Audit and naming: **`docs/development/SCRAPING_DIRECTORY_AUDIT.md`** (now ingestion, Option B)
- Document schema: **`docs/concept_guides/MONGODB_CORPUS_SCHEMA.md`**
