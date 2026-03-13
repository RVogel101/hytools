# scripts/ vs. ingestion — Evaluation

**Question:** Should scripts in `scripts/` be moved under `ingestion/`?

**Short answer:** **No.** Keep `scripts/` at the project root. Only one script is a good fit to move under ingestion; the rest are one-off migrations, OCR helpers, or ops and fit better as top-level scripts or under other packages.

---

## What’s in scripts/

| Script | Purpose | Ingestion fit? |
|--------|--------|----------------|
| **migrate_book_inventory_to_mongodb.py** | One-time migration: JSONL (book inventory + author profiles) → MongoDB | **Weak.** Loads **entity** data (books, authors) used by discovery/research, not document text. Uses `ingestion.discovery` (BookInventoryManager, AuthorProfileManager). Conceptually “bootstrap discovery data,” not a pipeline stage. **Keep in scripts.** |
| **import_etymology_from_wiktextract.py** | Wiktextract/kaikki JSONL → MongoDB `etymology` collection | **No.** Etymology/lexicon import; lives in **linguistics** (etymology_db). Not document ingestion. **Keep in scripts** (or later under `linguistics/` as a CLI). |
| **ocr_page_stats.py** | Report per-page OCR yield (chars/words) for `page_*.txt` | **No.** Pure **OCR** post-processing; no MongoDB. **Keep in scripts** or under `ocr/` as a small CLI. |
| **ocr_textbook_modern_wa.py** | OCR one textbook PDF → per-page .txt + one concatenated extract | **No.** **OCR** one-off for a specific asset. **Keep in scripts** or under `ocr/`. |
| **upload_sources_to_gridfs.py** | Upload PDFs/images under a path to MongoDB GridFS (e.g. mss_nkr, gomidas) | **Yes.** Puts **source binaries** into the same backend ingestion uses; often run before or alongside acquisition. Only script that clearly fits “getting assets into the corpus store.” **Optional:** move to `ingestion/tools/` or keep in scripts. |
| **request_dpla_api_key.ps1 / .sh** | One-off HTTP request to get a DPLA API key | **No.** **Ops/setup**; no ingestion logic. **Keep in scripts** (or `docs/development/requests_guides/`). |

---

## Ongoing purpose vs one-off

| Script | Purpose type | Notes |
|--------|--------------|--------|
| **upload_sources_to_gridfs.py** | **Ongoing** | Run when adding new raw PDFs/images (mss_nkr, gomidas). → `ingestion/tools/`. |
| **ocr_page_stats.py** | **Ongoing** | Run after OCR to check per-page yield. → `ocr/`. |
| **ocr_textbook_modern_wa.py** | **Ongoing** (template) | OCR one PDF → pages + extract; reuse for other textbooks. → `ocr/`. |
| **import_etymology_from_wiktextract.py** | **Ongoing** | Populate/update etymology from kaikki dumps. → `linguistics/`. |
| **migrate_book_inventory_to_mongodb.py** | **Rare** (migration/restore) | JSONL → MongoDB for new env. → `ingestion/discovery/`. |
| **request_dpla_api_key.ps1 / .sh** | **One-off** | Get DPLA key once per dev. → `docs/development/requests_guides/`. |

Only the DPLA key scripts are true one-offs; the rest have ongoing or recurring use.

---

## Why not move scripts under ingestion wholesale?

1. **Ingestion is pipeline + stages.** It’s built around `ingestion.runner` and stages (acquisition, extraction, enrichment, aggregation, validation). Scripts are **one-off or occasional** CLIs: migrations, OCR, API keys. Putting them inside ingestion would mix “run the pipeline” with “run this migration once” and “run this OCR helper.”

2. **Different owners.**  
   - **Etymology** → linguistics.  
   - **OCR** → ocr.  
   - **Book/author migration** → discovery/research (already under `ingestion.discovery`); the *script* is just a migration entry point.  
   - **GridFS upload** → only one that’s clearly “ingestion-adjacent.”

3. **Convention.** A top-level **scripts/** for one-off and cross-cutting CLIs is common and keeps the main packages (ingestion, ocr, linguistics, integrations) focused.

---

## Recommendation (implemented)

**`scripts/` has been removed.** Each script was relocated:

- **upload_sources_to_gridfs** → `ingestion/tools/upload_sources_to_gridfs.py` — `python -m ingestion.tools.upload_sources_to_gridfs --path ... --source ...`
- **migrate_book_inventory_to_mongodb** → `ingestion/discovery/migrate_book_inventory.py` — `python -m ingestion.discovery.migrate_book_inventory`
- **import_etymology_from_wiktextract** → `linguistics/tools/import_etymology_from_wiktextract.py` — `python -m linguistics.tools.import_etymology_from_wiktextract --jsonl ...`
- **ocr_page_stats** → `ocr/page_stats.py` — `python -m ocr.page_stats <dir>`
- **ocr_textbook_modern_wa** → `ocr/textbook_modern_wa.py` — `python -m ocr.textbook_modern_wa [pdf]`
- **request_dpla_api_key.ps1 / .sh** → `docs/development/requests_guides/` (same filenames)

---

## Summary

| Location | Entry point |
|----------|-------------|
| **ingestion/tools/** | `python -m ingestion.tools.upload_sources_to_gridfs` |
| **ingestion/discovery/** | `python -m ingestion.discovery.migrate_book_inventory` |
| **linguistics/tools/** | `python -m linguistics.tools.import_etymology_from_wiktextract` |
| **ocr/** | `python -m ocr.page_stats`, `python -m ocr.textbook_modern_wa` |
| **docs/development/requests_guides/** | request_dpla_api_key.ps1, request_dpla_api_key.sh |
