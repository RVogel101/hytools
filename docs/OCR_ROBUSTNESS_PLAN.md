# OCR Robustness Plan (hytools)

## Overview

This document captures the full implementation plan for robust OCR of Western Armenian + English PDF sources in hytools. The goal is to provide a reliable pipeline for mixed-language text, reduce blank pages and errors, and ensure traceable, audit-friendly output.

### Goals
- Maximize OCR accuracy for Armenian/English mixed content.
- Avoid brittle baseline that fails on low-quality scans.
- Enable multi-pass, best-score selection per page.
- Maintain precise metadata linking back to source page.

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
