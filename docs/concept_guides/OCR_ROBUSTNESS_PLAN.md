# OCR Robustness Plan (hytools)

## Overview

This document captures the full implementation plan for robust OCR of Western Armenian + English PDF sources in hytools. The goal is to provide a reliable pipeline for mixed-language text, reduce blank pages and errors, and ensure traceable, audit-friendly output.

### Goals
- Maximize OCR accuracy for Armenian/English mixed content.
- Avoid brittle baseline that fails on low-quality scans.
- Enable multi-pass, best-score selection per page.
- Maintain precise metadata linking back to source page.

---

## Table and sparse multi-column layout (priorities A–E)

Implemented in `hytools.ocr` to mitigate **global Tesseract** failures on **multi-column pages, tables, and sparse text** (one PDF-wide pass collapsing columns).

| Priority | Mechanism | Module / behavior |
|----------|-----------|-------------------|
| **A** | PDF **text layer** first | `pdf_text_layer.try_text_layer_page` — PyMuPDF `get_text` when embedded glyphs look acceptable; skips raster OCR for that page. |
| **B** | **Column splits** | `layout_strategies.vertical_valley_column_bounds`, `ocr_column_strips` — vertical ink projection valleys → OCR per column, left-to-right. |
| **C** | **PSM 6 / 11 / 12** | `layout_strategies.best_sparse_psm_variant` — score OCR output and pick best sparse/block mode. |
| **D** | **Reading order** | `layout_strategies.reassemble_reading_order_from_boxes` — word boxes from `image_to_data`, sort by line then x. |
| **E** | **Vector tables** | `pdf_tables_vector.try_vector_tables` — optional **Camelot** then **Tabula** for vector-drawn tables (no OCR). |

**Pipeline flags** (`hytools.ocr.pipeline.ocr_pdf` and `config/settings.yaml` under `ocr`):

- `use_text_layer` (default `true`) — try **A** before rendering the page.
- `layout_fallback` (default `false`) — run **B/C/D** via `run_layout_fallbacks` and keep the best-scoring text; baseline confidence gating is skipped so recovery works when default PSM scores poorly.
- `try_vector_tables` (default `false`) — append `--- vector tables ---` blocks from **E** when libraries are installed.
- `vector_tables_prefer` — `"camelot"` or `"tabula"` (try order for **E**).

**Dependencies:** `pip install hytools[ocr]` for NumPy, Pillow, Tesseract bindings, pdf2image, OpenCV, PyMuPDF. Table extras: `pip install hytools[ocr-tables]` (may require Ghostscript for Camelot — see upstream docs).

---

## 1. Problem summary

- Armenian letters misrecognized (e.g., `հ` -> `ճ`/`Տ`).
- punctuation errors (`,` -> `չ`).
- broken up words (e.g., `Հայաստան` -> `Հայ_astanach`).
- reduced line counts due to segmentation failures.

---

## 2. Pre-OCR document classification

1. Preflight quality tests:
  - PDF page count & digital metadata.
  - image resolution, skew, color/grayscale.
  - page type categories (pure/ mixed/ dictionary/ table/ non-text).

2. Category-based strategy:
  - pure WA: `hye`, `psm=6`.
  - mixed WA/ENG: `hye+eng`, `psm=6`.
  - dictionary-style: `psm=1`, block segmentation.
  - table-like: optional layout tool path (OCRmyPDF / Kraken).

---

## 3. Per-page mixed language handling

- Run initial OCR in mixed mode `hye+eng`.
- Compute script ratio and identify mixed pages.
- On mixed pages, use `image_to_data` and bounding-box clustering:
  - split into Armenian-only / English-only zones
  - rerun OCR on each zone with proper language
  - recombine in reading order

---

## 4. Adaptive DPI multi-pass (including lower DPI)

Baseline:
- `dpi=300`, `hye+eng`, `psm=6`, `sauvola`, `confidence_threshold=60`

Retry sequence for weak/blank:
1. `adaptive_dpi=True`
2. `dpi=400` + `font_hint=tiny`
3. `dpi=500` + `psm=1`
4. `dpi=250` + `psm=6` (lower DPI alternative)
5. `dpi=200` (optional for extreme blur)

Select best per-page by score:
- `score = mean_conf * log(1 + len(text))`
- include script ratios and block accuracy.

---

## 5. Blank page handling and manual review

- Define blank: postprocessed text `.strip() == ""`.
- Re-run blank pages with progressive settings (steps from section 4).
- If still blank, label `needs human scan check`.
- Keep `page_####.jpg` sample for inspection.
- Provide review queue output.

---

## 6. Metadata tracking and traceability

For each page output store:
- source file and page number
- OCR attempt metadata (dpi, psm, lang, binarization, adaptive, font hint)
- mean confidence, char counts, Armenian/Latin ratios
- `source_language_code` from source (non-inferred)
- `internal_language_branch` from dialect classifier
- output path and status (`ok/weak/blank/manual-review`)

---

## 7. Post-OCR correction rules

1. Lexicon-based corrections for frequent confusions:
   - ΖԱԼ etc.
   - '`ճ`' to '`հ`' at word start if lexicon match
   - punctuation (`չ` to `,`) corrections
2. Context-aware replacements via Armenian vocabulary.
3. Train WA+ENG post-correction model later.

---

## 8. ML-backed enhancements (future)

1. Train a post-correction seq2seq model using OCR raw vs ground truth.
2. Chunked language detection (per-N-chars) to dynamically choose language.
3. Hybrid OCR path (OCRmyPDF/Kraken/GROBID + Tesseract) for hard pages.

---

## 9. Production metrics and monitoring

- track blank/weak page rates per file.
- alert when >10% blank/low-confidence pages.
- keep a problem file list for manual audit.
- log retries and final page status.

---

## 10. Implementation steps with effort estimates

- Preflight classification: 1-2 days
- Mixed-phase block OCR: 2-3 days
- DPI multi-pass, up/down: 2 days
- Metadata + trace: 1 day
- Post-correct rules: 1-2 days
- Manual review queue: 2 days
- ML prototype: 1 week (optional)
- Hybrid approach experiments: 1-2 weeks

---

## 11. Policy summary

- Start with `hye+eng` by default for mixed content.
- Keep source language tags in metadata, do not infer as final branch.
- Derive dialect only from text classifier/branch.

---

## 12. Review and quality gating

- Build preflight + report script (`analyze_output()` and page-level metrics).
- Match each output text to source page and attempt in JSON sidecar.
- Periodically check for common OCR transitions (`հ`→`ճ`, `,`→`չ`).

---

## 13. Notes from sample error (page_0305)

- mismatch `հազալ` vs `ճազալ`: fix with lexicon + confusion rules.
- `report Հայաստան` vs output split: adjust segmentation + word join.
- line count mismatch: use precise `psm=1`/block detection and tune line breaks.

---

## 14. External projects: approaches relevant to hytools

This section compares three public GitHub projects to the current hytools stack (`hytools.ocr.pipeline`, `reprocess_textbook_ocr.py`, `ocr_ingest.py`) and records ideas worth adopting or benchmarking against.

### 14.1 Current hytools baseline (for comparison)

- **Tesseract** with `hye+eng`, per-page language, PSM tuning.
- **Preprocessing**: Sauvola/Niblack/Otsu, adaptive DPI, font hints (`hytools.ocr.preprocessor`).
- **Multi-pass retries** with confidence thresholds and optional **TrOCR** fallback (`reprocess_textbook_ocr.py`).
- **Post-processing** (`hytools.ocr.postprocessor`) and planned lexicon / zone-based improvements (sections 3, 7).

---

### 14.2 [portmind/armenian-ocr](https://github.com/portmind/armenian-ocr)

**What it is:** A **two-stage** pipeline: **CRAFT**-style word detection → **recognition** (deep-text-recognition-benchmark–style), trained for Armenian plus Latin/Cyrillic, aimed at scanned documents with varied layout and quality. Optional **`--layout`** for paragraph/row structure. Models are distributed separately (S3); project uses Poetry. **License:** CC BY-NC 4.0 — verify compatibility before redistribution or commercial use.

**Relevance to hytools:**

- Aligns with **section 8** (hybrid / ML-backed paths): detection + recognition on crops is a concrete alternative when global Tesseract segmentation fails.
- **Hard pages:** consider this stack for pages where Tesseract returns blank, very low confidence, or garbage script ratios—complementary to TrOCR-only fallback.
- **Layout metadata:** their layout output is comparable to the **zone-based / reading-order** goals in section 3.
- **Evaluation:** they report character error rates vs Google Vision on a small annotated set; a similar **per-page benchmark** on textbook ground truth would help choose Tesseract vs this path.

**Effort:** high (separate inference stack, model download, integration glue).

---

### 14.3 [AtecAi/Armenian-Words-Lexicon-and-OCR-Dataset](https://github.com/AtecAi/Armenian-Words-Lexicon-and-OCR-Dataset)

**What it is:** Scripts to scrape **Armenian Wiktionary**, normalize case variants, and **generate synthetic word images** (fonts + augmentations) for **training** OCR or building **lexicons**. Full image datasets are large and not committed; generated outputs are produced locally.

**Relevance to hytools:**

- Directly supports **section 7** (lexicon-based post-OCR correction): word lists can back spell-check, confusion fixes, or “did you mean” even if scraped vocabulary is not Western-only (filter or weight toward WA).
- If hytools later **fine-tunes** a line recognizer or TrOCR, synthetic rendered lines follow the same pattern as their `generator.py` workflow.

**Effort:** medium for lexicon integration; higher if training custom recognition models.

---

### 14.4 [Serge-Ordanyan/armenian-ocr-toolkit](https://github.com/Serge-Ordanyan/armenian-ocr-toolkit)

**What it is:** **Tesseract + Pillow + pdf2image** with **multiple preprocessing strategies run in parallel**, combined language **`hye` + `arm`** (standard + older Armenian trained data), **~600 DPI** rasterization, and **side-by-side text outputs** so the best run can be chosen manually—tuned for old or difficult prints.

**Relevance to hytools:**

- **Ensemble philosophy:** matches multi-pass / `page_NNN_tryK.txt` style runs; could add an explicit branch: **morphological dilation** (stroke repair) before OCR, as they prioritize for degraded type.
- **`hye+arm`:** hytools often uses `hye+eng`; an extra pass with **`hye+arm`** (or `arm` alone) on stubborn pages may help classical orthography and older fonts.
- **DPI:** try **500–600 DPI** on worst pages vs current 300–400 baseline (cost: memory/time).

**Effort:** low to medium (extra preprocessor branch + CLI flags).

---

### 14.5 Prioritized ideas (from external review)

| Idea | Source | Effort |
|------|--------|--------|
| Add `hye+arm` pass on low-confidence pages | armenian-ocr-toolkit | Low |
| Stroke-thickening / dilation preprocessor branch; score vs Sauvola-only | armenian-ocr-toolkit | Low–medium |
| One-off **600 DPI** pass for selected bad pages | armenian-ocr-toolkit | Low |
| Import or build **word lexicon** for post-OCR correction | AtecAi-style + §7 | Medium |
| Optional **CRAFT + recognizer** path for failure cases | portmind | High |
| Layout / line grouping metadata | portmind `--layout` concept | Medium–high |

---

### 14.6 Western Armenian policy

- **Target dialect for corpus text remains Western Armenian** (see project transliteration / dialect rules).
- **Tesseract `hye`** and generic “Armenian” lexicons may skew Eastern; use external models and lexicons as **assistive** (detection, CER benchmarks, spelling hints), not as unfiltered truth.
- Keep **WA validation / dialect tagging** on ingest (`ocr_ingest`, filters) as the gate for what enters the corpus.
