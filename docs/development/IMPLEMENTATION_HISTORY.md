# Implementation History (armenian-corpus-core)

Record of features that have been implemented. For current backlog and ideas, see [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md).

---

## Metrics and augmentation

| Feature | Notes |
|--------|-------|
| **Metrics visualization** | `runner visualize` subcommand; loads augmented docs from MongoDB, plots metric distribution, writes analysis report. Run: `python -m augmentation.runner visualize --metric lexical_ttr --output cache/metric_plots`. |
| **Drift detection on ingest** | Optional in `insert_or_skip` via `drift_check_on_ingest`; loads WA/EA baseline, z-scores for TTR and dialect purity, stores `metadata.drift_check` when anomalous. Config: `database.drift_check_on_ingest`, `drift_z_threshold`. |
| **Metrics pipeline integration** | `compute_metrics_per_task` flag; BatchWorker runs compute_baseline + compute_augmented per task, stores in MongoDB. |
| **Per-document metrics on ingestion** | `compute_metrics_on_ingest`; TextMetricCard + loanwords + word_counts in `metadata.document_metrics`. See `docs/LOANWORD_TRACKING_ANALYSIS.md`. |

---

## Dialect and linguistics

| Feature | Notes |
|--------|-------|
| **Dialect classifier Classical (hyc / xcl)** | Rule-based classical label in `linguistics/dialect_classifier.py`; `Dialect.CLASSICAL_ARMENIAN`, `DialectSubcategory.CLASSICAL_LITURGICAL` in `scraping/metadata.py`; language_code **xcl**. See `docs/CLASSICAL_ARMENIAN_IDENTIFICATION.md`. |
| **Armenian sub-classifying + clustering** | `linguistics.dialect.dialect_clustering`: `--mongodb`, `--sweep`, `--save-mongodb`; PCA + DBSCAN, sweep results and per-document cluster labels in MongoDB. |

---

## OCR

| Feature | Notes |
|--------|-------|
| **OCR language-aware Tesseract** | `per_page_lang`: off | auto | hye | hye+eng | eng; `tesseract_lang_armenian/mixed/english`; script ratio from probe text. Config in `ocr/` and `config/settings.yaml`. |

---

## Research pipeline

| Feature | Notes |
|--------|-------|
| **Research pipeline** | Centralized `ingestion._shared.research_config` (config key `research.*`); exclude_dirs/sources, error_threshold_pct; `extract_authors_from_corpus(..., return_stats=True)`; pipeline fails if error rate > threshold. |

---

## Scraping and sources

| Feature | Notes |
|--------|-------|
| **LOC** | Adaptive 429/Retry-After, X-RateLimit-* handling; parallel metadata fetch (ThreadPoolExecutor, batch 6, pool 3); config passed to insert_or_skip; status from `data/logs/loc_background_errors.log`; progress every 20 items. |
| **Gallica, DPLA, Gomidas** | Implemented. See `docs/DATA_SOURCES_API_REFERENCE.md`. |
| **Unified scraper CLI** | `python -m scraping.runner` with `run`, `status`, `list`, `dashboard`. |
| **Dashboard** | `python -m scraping.runner dashboard [--output data/logs/scraper_dashboard.html]` generates HTML with document counts per source. |

---

## Word frequencies and book catalog

| Feature | Notes |
|--------|-------|
| **Word frequencies: multi-dimensional facets** | Collection `word_frequencies_facets`; facets: author, source, dialect, year, region. Built from `word_counts`; aggregate and query CLI/API in `scraping.word_frequency_facets`. |
| **Word frequencies: target-weighted** | Config `scraping.frequency_aggregator.target_*_pct`; dynamic weights from current vs target distribution; metadata stores weights and target_pcts. |
| **Book catalog: MongoDB** | `BookInventoryManager` requires MongoDB; no JSONL fallback. Migration: `python -m ingestion.discovery.migrate_book_inventory`. |

---

## HathiTrust (partial)

| Feature | Notes |
|--------|-------|
| **Bibliographic API fallback** | When full text unavailable, catalog metadata stored. Stub `load_htrc_bulk()` for HTRC bulk; full bulk requires HTRC membership. |

---

## Code quality (addressed)

| Issue | Fix |
|-------|-----|
| **Matplotlib legend** | `ax.legend()` only when `get_legend_handles_labels()[0]` (in `augmentation/metrics_visualization.py`). |
| **NumPy empty-slice** | `_safe_mean()` and `np.nanmean` in `generate_analysis_report`; empty lists yield 0.0. |

---

*Last updated from FUTURE_IMPROVEMENTS.md audit and section cleanup.*
