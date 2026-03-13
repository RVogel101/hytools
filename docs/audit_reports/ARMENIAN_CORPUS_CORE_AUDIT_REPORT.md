# Armenian-Corpus-Core — Audit Report

**Audit Date:** 2026-03-08  
**Scope:** Package structure, CI/CD, data flow, augmentation, scraping, and documentation.

---

## 1. CI/CD Automation — What It Is and Implications

### What Is CI/CD?

**CI/CD** stands for **Continuous Integration** and **Continuous Delivery/Deployment**:

- **Continuous Integration (CI):** Automatically build, test, and validate code whenever changes are pushed (e.g. on every commit or pull request). Catches integration issues early.
- **Continuous Delivery (CD):** Automatically prepare and deliver artifacts (e.g. built packages, reports) so they can be deployed or used without manual steps.
- **Continuous Deployment:** Automatically deploy to production after successful CI. (Often not used for research/corpus projects.)

### What This Project Has

The project uses **GitHub Actions** for CI/CD:


| Component         | Location                         | Purpose                                     |
| ----------------- | -------------------------------- | ------------------------------------------- |
| Scraping workflow | `.github/workflows/scraping.yml` | Scheduled and manual scraping pipeline runs |


**Triggers:**

- **Weekly (Mondays 03:00 UTC):** Wikipedia, Wikisource, Archive.org, HathiTrust, LOC
- **Daily (06:00 UTC):** Newspapers, Eastern Armenian news, CulturaX, RSS, English sources
- **Manual:** `workflow_dispatch` with configurable stages

**Steps:**

1. Checkout code, install package (`pip install -e '.[all]'`)
2. Restore cache (`data/raw/`, `data/logs/`, `data/frequencies/`)
3. Ingest cached JSONL into MongoDB (`integrations.database.run_ingestion`)
4. Determine stages from schedule or manual input
5. Run scraping pipeline (`scraping.runner run`)
6. Upload artifacts: `pipeline_summary.json`, frequency lists

### Implications


| Implication                | Description                                                                            |
| -------------------------- | -------------------------------------------------------------------------------------- |
| **Automated data refresh** | Corpus data is refreshed on a schedule without manual runs.                            |
| **Reproducibility**        | Same steps run in a controlled environment (Ubuntu, Python 3.12, MongoDB 7).           |
| **Artifact retention**     | Pipeline summary and frequency lists are stored as GitHub artifacts (30–90 days).      |
| **MongoDB dependency**     | CI uses a MongoDB service container; scraping and ingestion require MongoDB.           |
| **No local storage in CI** | Output goes to MongoDB; local JSON/CSV for metrics is deprecated.                      |
| **Cache behavior**         | Cache key includes `run_number`; cache is best-effort and may not persist across runs. |


### What Is Not Automated (Yet)

- **Tests:** No dedicated test workflow (e.g. `pytest` on push/PR).
- **Augmentation:** Augmentation pipeline is not run in CI.
- **Cleaning:** Cleaning runs as part of scraping when `cleaning` stage is enabled; not a separate workflow.
- **Book catalog / author research:** Run locally or via cron/systemd (see `docs/LOCAL_SCHEDULER.md`).

---

## 2. Package Structure

### Flat Packages (Current)

The project uses **flat packages** only. The legacy `armenian_corpus_core` package does not exist.


| Package          | Purpose                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| `scraping`       | Data acquisition (Wikipedia, LOC, newspapers, etc.), registry, metadata |
| `cleaning`       | Text normalization, WA filtering, MongoDB cleaning                      |
| `augmentation`   | LLM-based augmentation, metrics, drift detection                        |
| `linguistics`    | Dialect distance, text metrics, vocabulary filter                       |
| `ocr`            | Tesseract pipeline, preprocessing, cursive detection                    |
| `research`       | Book inventory, author research, coverage analysis                      |
| `integrations`   | MongoDB client, run_ingestion, Anki                                     |
| `core_contracts` | Types, hashing, domain contracts                                        |


### Import Conventions

- Use `ingestion.discovery.book_inventory`, `ingestion.acquisition.loc`, `augmentation.runner`, etc.
- Do **not** use `armenian_corpus_core.`* or `src.*` — these are removed.
- See `docs/IMPORT_REDIRECTS.md` for full mapping.

---

## 3. Data Flow and Persistence

### Primary Storage: MongoDB


| Collection             | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| `documents`            | Scraped/cleaned text, metadata, dialect tags        |
| `augmented`            | Augmented documents (when `output_backend=mongodb`) |
| `book_inventory`       | Book catalog (when config has `mongodb_uri`)        |
| `augmentation_metrics` | Per-task and batch metric cards, reports            |
| `word_frequencies`     | Aggregated word counts by source                    |
| `catalogs`             | LOC, archive_org, etc. catalog state                |


### No Local JSON/CSV for Metrics

- **Metrics pipeline:** All output goes to MongoDB (`augmentation_metrics`). No `cache/metric_cards/*.json` or CSV export.
- **Book inventory:** When MongoDB is configured, inventory is stored in `book_inventory`; no `data/book_inventory.jsonl`.

### Local Files (Minimal)


| Path                   | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `data/raw/`            | Cached JSONL before ingestion (CI restores from cache) |
| `data/logs/`           | Pipeline summary, runner logs                          |
| `data/frequencies/`    | Frequency lists (also uploaded as artifacts)           |
| `config/settings.yaml` | Pipeline configuration                                 |


---

## 4. Implementation Summary (Recent Changes)

### Metrics Pipeline → MongoDB Only

- `MetricsComputationPipeline` takes `mongodb_client`; per-task cards and batch reports stored in `augmentation_metrics`.
- `runner metrics` removed `--out` and `--export-csv`; all output to MongoDB.

### Cursive Detection in OCR

- `ocr/preprocessor.py`: `estimate_cursive_likelihood()` (contour elongation, stroke-width variance).
- `binarize()` and `preprocess()` support `cursive_mode` (Niblack/Sauvola, smaller block, optional morphology).
- Config: `detect_cursive`, `cursive_threshold` in `config/settings.yaml`.

### Scraping Workflow

- Stage names aligned with runner: `wikipedia_wa`, `wikipedia_ea`, `ea_news`, `loc`, etc.
- Artifact path: `data/logs/pipeline_summary.json`.
- Ingestion step: `integrations.database.run_ingestion --raw-only` before scraping.

### Run Ingestion Script

- `integrations/database/run_ingestion.py`: Loads cached JSONL from `data/raw/` into MongoDB.
- Used by CI; available for manual runs.

### LOC and Background Design

- LOC is a normal pipeline stage (like archive_org, hathitrust).
- Background: `scraping.runner run --background` (full pipeline) or `scraping.loc run --background` (LOC only).
- See `docs/SCRAPING_RUNNER_AND_LOC.md`.

### Book Catalog MongoDB

- `BookInventoryManager` uses MongoDB when `config` has `database.mongodb_uri`.
- `book_inventory_runner` defaults to `config/settings.yaml`.
- Migration: `python -m ingestion.discovery.migrate_book_inventory --config config/settings.yaml`.

### Import Cleanup

- Removed `armenian_corpus_core` and `src` fallbacks across research, augmentation, cleaning, tests.
- All imports use flat packages.

### Local Scheduler

- `docs/LOCAL_SCHEDULER.md`: Cron and systemd examples for scraping, cleaning, augmentation, book catalog, author research.

---

## 5. Component Status


| Component            | Implemented | Integrated | Notes                                 |
| -------------------- | ----------- | ---------- | ------------------------------------- |
| scraping.runner      | ✅           | ✅          | Central pipeline entry point          |
| cleaning.run_mongodb | ✅           | ✅          | Via `scraping.runner --only cleaning` |
| augmentation.runner  | ✅           | ✅          | CLI: estimate, run, status, metrics   |
| augmentation metrics | ✅           | ✅          | MongoDB only; `runner metrics`        |
| run_ingestion        | ✅           | ✅          | CI + manual                           |
| book_inventory       | ✅           | ✅          | MongoDB when config present           |
| cursive detection    | ✅           | ✅          | OCR preprocessor                      |
| CI scraping workflow | ✅           | ✅          | Weekly + daily + manual               |


---

## 6. Recommendations

1. **Add a test workflow** — Run `pytest` on push/PR to catch regressions.
2. **Document CI limitations** — Cache and MongoDB are ephemeral in CI; document expectations for artifact retention.
3. **Optional: augmentation in CI** — If desired, add a separate workflow or stage for augmentation (requires LLM availability).
4. **Keep metrics MongoDB-only** — No reintroduction of local JSON/CSV for metrics.

---

## 7. Related Documentation


| Document                                                 | Purpose                        |
| -------------------------------------------------------- | ------------------------------ |
| `docs/IMPORT_REDIRECTS.md`                               | Flat package mapping           |
| `docs/SCRAPING_RUNNER_AND_LOC.md`                        | Runner design, LOC, background |
| `docs/LOCAL_SCHEDULER.md`                                | Cron/systemd examples          |
| `docs/SOURCE_DOCUMENT_STORAGE_AND_AUGMENTATION_AUDIT.md` | Storage and augmentation audit |
| `docs/FUTURE_IMPROVEMENTS.md`                            | Planned work                   |
| `docs/DATA_PERSISTENCE_AND_FILE_USAGE.md`                | Data storage overview          |


