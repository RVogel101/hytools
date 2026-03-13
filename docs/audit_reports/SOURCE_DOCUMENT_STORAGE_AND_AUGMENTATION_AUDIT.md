# Source Document Storage & Augmentation Directory Audit

**Update:** GridFS implemented. See `integrations/database/mongodb_client.py` (upload_source_binary, download_source_binary_to_path, find_source_binaries). OCR ingest can stream from GridFS via `scraping/ocr_ingest.py` (ingest_from_gridfs).

## Part 1: PDF/Image Storage for OCR

### Can Tesseract take PDF better?

**Short answer:** Tesseract does not process PDFs directly. Your `ocr/pipeline.py` already does the right thing: it uses `pdf2image.convert_from_path()` to rasterize each PDF page to images at a configurable DPI (default 300), then runs Tesseract on those images.

**What actually affects quality:**
- **Resolution (DPI):** 300 DPI is the recommended minimum. Higher DPI can help for small or degraded text but increases memory and time.
- **Preprocessing:** Your `ocr/preprocessor.py` (binarization, deskewing, denoising) improves results.
- **Format:** PDF vs image is irrelevant once converted—quality depends on the rasterized image, not the original format.

So: PDFs are not inherently "better"; they are converted to images first. Your pipeline is correct.

---

### Recommendations for Storing Source Documents (PDFs/Images) as Backup

You want: centralized, organized storage; one-time dumps that may never be available again; delete everything else after moved to MongoDB.

#### Option A: MongoDB GridFS (Centralized, No Local Files)

**How it works:**
1. Download PDF/image → store in GridFS with metadata (source, date, identifier).
2. When OCR needed: stream from GridFS to a temp file → run Tesseract → insert text to `documents` → delete temp file.
3. Source binaries stay in MongoDB; no persistent local storage.

**Pros:** Single source of truth; no scattered files; survives machine loss.
**Cons:** Temp-file streaming adds code; GridFS has 16MB chunk limit per file (large PDFs split automatically).

**Implementation sketch:**
- Add `source_binaries` GridFS bucket in MongoDB.
- `ocr_ingest` or a new `ingest_from_gridfs` module: for each GridFS file, `get()` to temp, OCR, delete temp.
- Scrapers (mss_nkr, gomidas, etc.) write to GridFS instead of `data/raw/` when `paths.store_sources_in_gridfs: true`.

---

#### Option B: Single Organized Directory (Simpler)

**Structure:**
```
data/source_archive/
├── mss_nkr/
│   └── 2025-03-08/
│       └── document_123.pdf
├── gomidas/
│   └── newspaper_xyz.pdf
└── one_time_dumps/
    └── hathitrust_batch_001/
        └── *.pdf
```

**How it works:**
1. All scrapers write to `paths.source_archive_dir` (e.g. `data/source_archive/{source}/`) instead of scattered `data/raw/*`.
2. OCR reads from there; after successful ingest, delete file when `paths.delete_after_ingest: true`.
3. Optional: keep a manifest JSON in each subdir listing what was ingested (for audit).

**Pros:** Simple; no MongoDB changes; easy to browse/backup.
**Cons:** Still local disk; need to back up this dir separately if you want durability.

---

#### Option C: Hybrid (GridFS + Temp for OCR)

1. **Ingest phase:** Download → store in GridFS → optionally delete local copy.
2. **OCR phase:** For each GridFS file, stream to temp → OCR → insert text → delete temp.
3. Source binaries only in MongoDB; zero persistent local storage for sources.

**Recommendation:** For "one-time dumps" and "delete everything else after moved to MongoDB," **Option C (GridFS)** is the cleanest. Implement a small helper:

```python
def ocr_from_gridfs(file_id: str, client, temp_dir: Path) -> str | None:
    """Stream GridFS file to temp, OCR, return text. Caller deletes temp."""
    with client.open_download_stream(file_id) as stream:
        path = temp_dir / "ocr_input.pdf"
        with open(path, "wb") as f:
            for chunk in stream:
                f.write(chunk)
    return _ocr_single_file(path, temp_dir, ...)
```

---

### Delete Everything Else After Moved to MongoDB

With `paths.delete_after_ingest: true` in config:
- Wikipedia bz2: deleted after extraction.
- mss_nkr PDFs/images: deleted after OCR (in `mss_nkr._ingest_text_files_to_mongodb`).
- ocr_ingest: deletes each file after successful ingest.

Ensure all ingest paths honor this flag. Then only `config/` and `data/logs` persist locally (plus `data/source_archive` if you use Option B and choose to keep backups).

---

## Part 2: Augmentation Directory Audit

### File-by-File Summary

| File | Purpose | Upstream | Downstream | Status |
|------|---------|----------|------------|--------|
| `batch_worker.py` | Core engine: scan docs, build tasks, run strategies, write output, checkpoint | MongoDB or `data/cleaned` | MongoDB or `data/augmented` | ✅ Implemented |
| `runner.py` | CLI: estimate, run, status, background | config/settings.yaml | batch_worker | ✅ Implemented |
| `strategies.py` | LLM + non-LLM transforms (paraphrase, continue, topic_write, shuffle, deletion, dropout) | llm_client, linguistics.metrics | batch_worker | ✅ Implemented |
| `llm_client.py` | HTTP client for Ollama/OpenAI-compatible LLM | — | strategies | ✅ Implemented |
| `safe_generation.py` | Rejection-sampling wrapper for WA-only output | strategies, validate_augmentation_output | batch_worker (when `use_safe_wrapper: true`) | ✅ Plugged in via config |
| `baseline_statistics.py` | Corpus baseline stats (mean, std, percentiles) for metrics | text_metrics, MongoDB/corpus | drift_detection, metrics_visualization | ⚠️ Standalone |
| `metrics_pipeline.py` | Compute baseline + augmented metrics, compare, export | text_metrics | `runner metrics` | ✅ Plugged in via runner |
| `metrics_visualization.py` | Plot metric distributions, anomalies | baseline_statistics, metric_cards | — | ⚠️ Standalone |
| `drift_detection.py` | Anomaly/drift alerts from metric batches | baseline_statistics | — | ⚠️ Standalone |
| `calibrate_distance_weights.py` | Optimize WA/EA dialect distance weights | benchmark_dialect_distance, dialect_distance | cache/dialect_distance_calibration.json | ✅ Fixed import |
| `benchmark_dialect_distance.py` | Benchmark dialect distance on WA/EA corpora | dialect_distance, local .txt dirs | cache/dialect_distance_benchmark.json | ✅ Fixed import |

---

### What’s Plugged In

**Main pipeline (working):**
```
ingestion.runner (cleaning) → MongoDB documents
         ↓
batch_worker (source_backend=mongodb) reads from MongoDB
         ↓
strategies (paraphrase, continue, etc.) + llm_client
         ↓
batch_worker writes to MongoDB (output_backend=mongodb) or data/augmented
```

- `runner.py` → `batch_worker.py` → `strategies.py` → `llm_client.py`: **connected**.
- **Safe generation:** Config `augmentation.use_safe_wrapper` (default True) wires `SafeAugmentationWrapper` in the batch worker.
- **Metrics:** `python -m augmentation.runner metrics` runs `MetricsComputationPipeline` on MongoDB augmented output; stores in `augmentation_metrics`.
- **Visualize:** `python -m augmentation.runner visualize` plots metric distributions (requires matplotlib).
- **Dialect distance:** calibrate/benchmark use `linguistics.metrics.dialect_distance` (see `docs/IMPORT_REDIRECTS.md`).

---

### What’s Not Plugged In

1. **`baseline_statistics.py`**  
   - Computes corpus-wide baseline stats for anomaly detection.  
   - Used by `drift_detection` and `metrics_visualization`; run manually (e.g. `python -m augmentation.baseline_statistics`) or as a pre-step before visualization.  
   - Not invoked automatically by the main augmentation flow.

2. **`drift_detection.py`**  
   - Consumes baseline stats and metric batches to produce alerts.  
   - Standalone; has `python -m augmentation.drift_detection` CLI.  
   - Run manually for quality monitoring.

3. **`metrics_visualization.py`**  
   - Plots metric distributions; **wired** via `python -m augmentation.runner visualize`.  
   - Loads metric cards from MongoDB; no separate standalone requirement for basic use.

---

### Imports (Fixed)

**`calibrate_distance_weights.py`** and **`benchmark_dialect_distance.py`** use:
```python
from linguistics.metrics.dialect_distance import DistanceWeights, compute_component_distance
```
Flat packages only. `armenian_corpus_core` does not exist. See `docs/IMPORT_REDIRECTS.md`.

---

### Duplicate / Overlapping Code

1. **Validation logic**  
   - `strategies.py` uses `validate_augmentation_output` from `linguistics.metrics`.  
   - `safe_generation.py` now delegates to `validate_augmentation_output` (no separate path).  
   - **Resolved:** Single validation path.

2. **Import paths**  
   - Augmentation modules use flat packages: `linguistics.*`, `augmentation.*`, `cleaning.*`. `armenian_corpus_core` does not exist.  
   - See `docs/IMPORT_REDIRECTS.md` for full mapping.

---

### Conflicting Processes

- **PID file:** `runner` uses `data/logs/.augmentation.pid` (when MongoDB output) or `data/augmented/.augmentation.pid` (filesystem). Only one augmentation process should run at a time; the PID file prevents accidental double-runs.
- **Checkpoint:** When using MongoDB, checkpoint is in `augmentation_checkpoint`; when filesystem, in `data/augmented/.checkpoint.jsonl`. No conflict if you stick to one backend.
- **Source vs output:** `source_backend` and `output_backend` can be mixed (e.g. MongoDB source + filesystem output). No inherent conflict.

---

### Summary Table

| Component | Implemented | Plugged In | Notes |
|----------|-------------|------------|-------|
| batch_worker | ✅ | ✅ | Core pipeline |
| runner | ✅ | ✅ | CLI: run, estimate, status, metrics, visualize |
| strategies | ✅ | ✅ | All strategies |
| llm_client | ✅ | ✅ | Ollama/OpenAI |
| safe_generation | ✅ | ✅ | Config `use_safe_wrapper` (default True) |
| baseline_statistics | ✅ | Manual | Run before drift/visualization if needed |
| metrics_pipeline | ✅ | ✅ | `runner metrics` subcommand |
| metrics_visualization | ✅ | ✅ | `runner visualize` subcommand |
| drift_detection | ✅ | Manual | Standalone CLI for monitoring |
| calibrate_distance_weights | ✅ | N/A | Uses linguistics.metrics.dialect_distance |
| benchmark_dialect_distance | ✅ | N/A | Uses linguistics.metrics.dialect_distance |

---

### Recommended Fixes (Priority Order)

1. ~~**Fix dialect_distance imports**~~ — Done. Uses `linguistics.metrics.dialect_distance` with fallback.
2. ~~**Standardize package imports**~~ — Done. Augmentation modules use try/except with `linguistics.*`, `augmentation.*`, `cleaning.*` first.
3. ~~**Optionally integrate SafeAugmentationWrapper**~~ — Done. Config `augmentation.use_safe_wrapper: true` (default).
4. ~~**Add a post-augmentation metrics step**~~ — Done. `runner metrics` runs `MetricsComputationPipeline` on MongoDB augmented output.
5. ~~**Add runner visualize**~~ — Done. `runner visualize` plots metric distributions.
6. ~~**Document** which scripts are standalone vs. main pipeline~~ — See `docs/concept_guides/AUGMENTATION_FAQ.md` and this audit.
