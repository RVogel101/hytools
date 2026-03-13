# Augmentation FAQ

## What is safe_generation.py and what does it do?

**safe_generation.py** implements **rejection sampling** for Western Armenian (WA) augmentation:

1. **SafeAugmentationWrapper** — Wraps any augmentation strategy (e.g. ParaphraseStrategy). When the strategy generates text, the wrapper validates it. If it fails WA checks, it retries (up to `max_attempts`). Returns only validated WA text or `None` if all attempts fail.

2. **BatchAugmentationRunner** — Applies safe augmentation to batches of texts and tracks success/failure stats.

**Why was it not used by batch_worker?**  
Phase 1 (SafeAugmentationWrapper) is **wired into the main pipeline** when `augmentation.use_safe_wrapper: true` in config (default: true). LLM strategies (paraphrase, continue, topic_write) are wrapped with rejection sampling for stricter Western Armenian guarantees.

**Now:** Config flag `augmentation.use_safe_wrapper: true` wraps LLM strategies in SafeAugmentationWrapper when enabled.

---

## What metrics/statistics are taken in baseline_statistics?

**Per-document metrics** (from `linguistics.metrics.text_metrics.TextMetricCard`):

| Category | Metrics |
|----------|---------|
| **Lexical** | TTR, STTR, Yule's K, unique words, total words |
| **Syntactic** | Avg sentence length, clauses per sentence, Flesch-Kincaid grade |
| **Morphological** | Suffix frequencies (-եմ, -իմ, -ում, -ան, -ել). See docs/MORPHOLOGICAL_SUFFIX_AND_PREFIX_TRACKING.md. No prefixes tracked. |
| **Contamination** | Code-switching index, Eastern form ratio |
| **Quality** | Dialect purity score (0–1) |

**Corpus baseline** (from `baseline_statistics`): For each metric, compute **mean, std dev, min, max, median, p25, p75** across all documents. Used for anomaly detection (e.g. flag texts >2σ from mean).

---

## Can baseline_statistics run on each document as it's ingested?

**Yes.** Two approaches:

1. **Per-document on ingest:** Compute a `TextMetricCard` for each document as it's inserted into MongoDB. Store the card (or key metrics) in the document's `metadata` or a separate `document_metrics` collection. Pros: real-time metrics; cons: ingest slowdown.

2. **Batch after ingest:** Run `baseline_statistics` as a separate job over MongoDB documents. Pros: no ingest impact; cons: baseline is computed periodically, not per-document.

**Recommendation:** Compute per-document metrics on ingest and store in `metadata.metrics` or a `document_metrics` collection. Run corpus baseline (mean, std, etc.) as a separate periodic job. This supports both per-document anomaly checks and drift detection.

---

## What does metrics_pipeline do vs baseline_statistics?

| Module | Purpose |
|--------|---------|
| **metrics_pipeline** | Per-text: `compute_baseline()` before augmentation, `compute_augmented()` after. Compares before/after. Saves metric cards. |
| **baseline_statistics** | Corpus-level: aggregates metric cards into mean, std, percentiles. Used for anomaly detection and drift. |

Both use the same underlying `TextMetricCard` from `linguistics.metrics.text_metrics`.

---

## Which scripts are main pipeline vs standalone analysis?

| Script | Role | Invocation |
|--------|------|------------|
| **batch_worker.py** | Core pipeline engine | Used by runner |
| **runner.py** | CLI entry-point | `python -m augmentation.runner estimate \| run \| status \| metrics` |
| **strategies.py** | LLM + non-LLM transforms | Used by batch_worker |
| **llm_client.py** | HTTP client for Ollama/OpenAI | Used by strategies |
| **safe_generation.py** | Optional WA rejection wrapper | Wrapped by batch_worker when `use_safe_wrapper: true` |
| **metrics_pipeline.py** | Per-text metrics, batch reports | Used by `runner metrics`; also importable |
| **baseline_statistics.py** | Corpus baseline (mean, std, percentiles) | `python -m augmentation.baseline_statistics --mongodb` or `--wa-dirs` / `--ea-dirs` |
| **drift_detection.py** | Anomaly/drift alerts | `python -m augmentation.drift_detection` |
| **metrics_visualization.py** | Plot metric distributions | Standalone; import and call functions |
| **calibrate_distance_weights.py** | Optimize WA/EA dialect weights | `python -m augmentation.calibrate_distance_weights --wa-dirs ... --ea-dirs ...` |
| **benchmark_dialect_distance.py** | Benchmark dialect distance configs | `python -m augmentation.benchmark_dialect_distance --wa-dirs ... --ea-dirs ...` |

**Main pipeline flow:** `runner run` → batch_worker → strategies → llm_client → MongoDB.

**Post-augmentation metrics:** `runner metrics` reads augmented documents from MongoDB and runs `MetricsComputationPipeline` on them. Output is stored in MongoDB only (`augmentation_metrics` collection). No local JSON or CSV.
