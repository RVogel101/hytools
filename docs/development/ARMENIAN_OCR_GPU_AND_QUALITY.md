# Armenian OCR: GPU Engines & Quality Tuning

## 1. Armenian support in PaddleOCR and EasyOCR (research)

### PaddleOCR

- **Official support:** Armenian (**hye**) is **not** in the official PaddleOCR supported languages list. Documented languages include Latin, Arabic, Chinese, Korean, Japanese, Hebrew (added 2024), and 80+ others — but not Armenian.
- **GPU:** PaddleOCR supports GPU (CUDA) and can be faster than Tesseract on batches.
- **Adding a language:** PaddleOCR has a documented process for adding new languages (training data, fine-tuning). Adding Armenian would require contributing a new model/dataset.
- **Third-party:** The [portmind/armenian-ocr](https://github.com/portmind/armenian-ocr) project (see §1.4 below) is a **custom detection+recognition pipeline** (CRAFT + deep-text-recognition-benchmark), not Tesseract or PaddleOCR; it supports GPU and is used at the National Library of Armenia.

**Conclusion:** PaddleOCR does **not** offer out-of-the-box Armenian. Using it for Armenian would require training or adapting a model (no ready-made hye or hye+eng).

### EasyOCR

- **Official support:** EasyOCR supports 80+ languages and scripts (Latin, Chinese, Arabic, Devanagari, Cyrillic, Thai, Korean, Japanese, Tamil, **Georgian (ka)**, etc.). **Armenian is not listed** among the documented supported languages.
- **GPU:** EasyOCR can use PyTorch with CUDA for inference.
- **Language codes:** Languages are specified by 2–3 letter codes (e.g. `en`, `ja`). There is no documented `hye` or Armenian code in the main docs.

**Conclusion:** EasyOCR does **not** offer out-of-the-box Armenian. Like PaddleOCR, using it for Armenian would require a custom model or a community contribution.

### Practical recommendation for Armenian

- **Current pipeline (Tesseract + hye/hye+eng)** remains the only common option with **native Armenian** support without training.
- **GPU:** Tesseract is CPU-only; if you need GPU acceleration for Armenian, you would need to either (1) train a PaddleOCR or EasyOCR model for Armenian, or (2) use a third-party project (e.g. [portmind/armenian-ocr](https://github.com/portmind/armenian-ocr) — custom trained, GPU-capable; or [ArmCor](https://github.com/decoder-99/ArmCor) for post-correction of Tesseract output). See **docs/development/FUTURE_IMPROVEMENTS.md** for a very low priority note on building your own model vs collaborating with existing projects.

### 1.4 portmind/armenian-ocr (investigation)

- **What it is:** Custom **Armenian document OCR** pipeline (not Tesseract, not PaddleOCR). Two-stage: **detection** (CRAFT — bounding boxes around words) and **recognition** (deep-text-recognition-benchmark). Supports Armenian plus **Latin** and **Cyrillic** in the same document.
- **Use case:** Scanned documents with different layouts, densities, and scan qualities. A modified version is used in digitization at the [National Library of Armenia](https://nla.am/en/).
- **GPU:** Supports **`--cuda`** for Nvidia GPU. Optional **`--layout`** for paragraph/row structure.
- **Quality:** Authors report ~4% mean character error rate vs ~5.5% for Google Cloud Vision OCR on their 4-document test set.
- **License:** CC BY-NC 4.0 (non-commercial use).
- **Install:** Poetry; model weights from S3 (`objects.zip`). Run `ocr.py` with paths to detection/recognition dirs and image path.
- **Collaboration:** Could be a candidate for integration or collaboration if we want GPU Armenian OCR without training from scratch; would require adapting their pipeline to our ingest (PDF → images → their OCR → text to MongoDB) and respecting their license.

---

## 2. OCR quality: missed words/letters and parameter tweaks

**Note:** I cannot open or view the PDF with computer vision. The analysis below is based on the **OCR output text** you shared (page_0039, page_0022, page_0049, page_0085) and on the pipeline code. Inferred causes are from typical Tesseract/preprocessing behavior and your described symptoms (missed words/letters).

### 2.1 Observed error patterns (from your samples)


| Page | Issue                                                            | Examples                                                                                                                       |
| ---- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 0039 | Character confusion (ճ/ձ/հ, digit “1” in text), line/block order | ճ1ոց, Տֆարուստ (for տարուստ), ճոգի (for ձոյր?), ոօ (for ոչ?), “ոզ church here”                                                 |
| 0022 | Sparse output; table/layout lost; wrong word boundaries          | Only a few words (պաղ, տաք, տղայ, ցտեսութիւն, քանի մը); rest missing or merged                                                 |
| 0049 | Almost only numbers; text in cells missing                       | 2, 3, 5, 6… 41 — suggests table/list where text wasn’t recognized                                                              |
| 0085 | Systematic glyph confusion, Latin intrusion                      | ճ↔հ (ճետաքրքրական→հետաքրքրական, Անաճիտ→Անահիտ), ն↔բ (բնկերուճիս), Պ↔հ (Պիւանդ→հիւանդ), “Suqneun” (Latin), ճամար/ճագուստ, ձսկայ |


**Likely causes:**

1. **Mixed script (hye+eng)** — Tesseract can mis-segment or confuse similar-looking Armenian and Latin (e.g. ճ/ր, ն/h, Պ/n).
2. **Page layout** — Tables, columns, or boxes (pages 0022, 0049) often break Tesseract’s default “automatic” layout; text in cells can be missed or merged.
3. **Font size / DPI** — Too small or wrong scale relative to Tesseract’s ideal ~20–30 px character height can increase confusion and drops.
4. **Binarization / contrast** — Weak contrast or binarization can drop strokes or merge characters (e.g. ճ/հ, ն/բ).
5. **Page segmentation mode (PSM)** — PSM 3 (fully automatic) can fail on textbooks with headers, footers, or tables; wrong PSM can skip or reorder blocks.

### 2.2 Parameters worth tweaking

These are in `ocr/pipeline.py`, `ocr/tesseract_config.py`, and `ocr/textbook_modern_wa.py` (run: `python -m ocr.textbook_modern_wa`).


| Parameter                   | Current     | Suggestion                                                              | Why                                                                                         |
| --------------------------- | ----------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **PSM (page segmentation)** | 3 (auto)    | Try **6** (uniform block of text) for body-text pages                   | Reduces layout confusion; better for single-column textbook body.                           |
| **PSM for tables**          | 3           | Try **4** (single column) or **11** (sparse text) for table-heavy pages | Can improve detection of text in cells (optional, per-page).                                |
| **DPI**                     | 300 (fixed) | Enable **adaptive_dpi=True** or try **250**                             | Gets character height into Tesseract’s sweet spot; 250 sometimes better for Latin/Armenian. |
| **confidence_threshold**    | 60          | Lower to **50** or **40** for problematic pages                         | Avoids skipping pages that still contain useful text with low mean confidence.              |
| **Binarization**            | sauvola     | Try **otsu** for clean, high-contrast scans                             | Can give sharper glyphs on good scans.                                                      |
| **Font hint**               | None        | Try **font_hint="normal"** (or “tiny” if text is small)                 | Nudges DPI toward 200–300 or 400+ (see pipeline).                                           |


### 2.3 Enabling adaptive DPI and PSM 6 in the textbook script

- **Implemented:** `ocr/textbook_modern_wa.py` (`python -m ocr.textbook_modern_wa`) now passes **PSM 6** (`PSM_BLOCK`) and **confidence_threshold=50** to the pipeline. Re-run the script (after deleting or moving existing `data/textbook_modern_wa_pages/*.txt` so pages are reprocessed) to compare output.
- In `ocr/tesseract_config.py`, **PSM_AUTO = 3** remains the default for other callers; the textbook script overrides with **PSM 6**.
- **Config for scraped/book PDFs:** To use the same textbook-friendly preset in the main OCR ingest (e.g. `scraping.ocr_ingest`), set in `config/settings.yaml`: `ocr.psm: 6` and optionally `ocr.confidence_threshold: 50`. The ingest pipeline reads these and passes them to `ocr_pdf()`.

### 2.4 Optional: per-page PSM or DPI

- **Tables (e.g. 0022, 0049):** Use PSM 4 or 11 only for pages detected as table-heavy (e.g. by ratio of blocks to text), or run a second pass with PSM 11 and merge.
- **Body text (e.g. 0085, 0039):** Prefer PSM 6 and adaptive DPI (or fixed 250).

### 2.5 Post-processing

- **[ArmCor](https://github.com/decoder-99/ArmCor)** (Armenian OCR correction) can fix common Tesseract confusions (e.g. ճ/հ, ն/բ) after OCR. Consider running it on `data/textbook_modern_wa_extract.txt` (or per-page) and then re-feeding corrected text into grammar/summarization.

---

## 3. Summary

- **PaddleOCR / EasyOCR:** No official Armenian (hye) or hye+eng; GPU use for Armenian would require a custom model. Tesseract remains the practical choice for Armenian.
- **Missed words/letters:** Likely due to layout (tables/columns), PSM, DPI/scale, and hye+eng confusion. Try **PSM 6**, **adaptive DPI** (or 250), and optionally **lower confidence_threshold** and **otsu** binarization.
- **Next step:** Add a config or script option for a “textbook” preset (e.g. PSM 6, adaptive_dpi=True, confidence 50) and re-run OCR on a few bad pages to compare; then run ArmCor on the full extract if available.

---

## 4. How to check if OCR is not picking up enough text (main pipeline)

When you run OCR on scraped PDFs or images (e.g. `ocr.pipeline`, `scraping.ocr_ingest`), use the following to detect low yield.

### 4.1 Pages skipped due to low confidence

- **Behavior:** In `ocr/pipeline.py`, any page whose **mean Tesseract confidence** is below `confidence_threshold` (default 60) is **not** written; no `.txt` file is produced for that page.
- **Check:** Run with **logging at INFO** (default). You will see:  
  `Page N: low confidence X.X (threshold 60), skipping`  
  for each skipped page. Count how many pages are skipped per run.
- **Action:** Lower `confidence_threshold` (e.g. 50 or 40) in `config/settings.yaml` under `ocr.confidence_threshold`, or in the script that calls `ocr_pdf()`, so that marginal pages still get text (then optionally post-correct or flag for review).

### 4.2 Per-page character/word count (low yield)

- **Behavior:** Even when a page is written, it may contain very little text (e.g. tables where only numbers were recognized).
- **Check:** Run a **per-page stats** pass on the output directory (e.g. `data/ocr_output/<source>/` or `data/textbook_modern_wa_pages/`):
  - List every `page_*.txt`, count characters and (optionally) words per file.
  - Flag pages below a threshold (e.g. &lt; 100 characters or &lt; 10 words) as likely "OCR not picking up enough text".
- **Script:** Use `python -m ocr.page_stats` (see below) or a one-off:  
  `for f in data/textbook_modern_wa_pages/page_*.txt; do echo "$f $(wc -c < "$f")"; done`  
  then sort by character count and inspect the smallest.

### 4.3 Documents skipped in ocr_ingest (short text)

- **Behavior:** In `scraping/ocr_ingest.py`, after OCR, any document with `len(text.strip()) < 50` is counted as **skipped_short** and not inserted into MongoDB.
- **Check:** Look at the ingest summary:  
  `OCR ingest: X inserted, Y duplicates, Z skipped (WA), N skipped (short), M errors`  
  If **skipped (short)** is high, many PDFs/images produced too little text (either bad OCR or mostly images/tables).
- **Action:** Lower the 50-character minimum in `ingest_directory`/`ingest_from_gridfs` if you want to keep marginal docs for manual review, or fix OCR settings (PSM, DPI, confidence) and re-run.

### 4.4 Optional: per-page confidence and yield report

- **Idea:** When running `ocr_pdf()`, optionally write a sidecar report (e.g. `pages_report.json` or `pages_report.csv`) with, per page: `page_num`, `char_count`, `word_count`, `mean_confidence`, `skipped` (true/false). Then you can sort by `char_count` or `mean_confidence` to find pages where OCR is not picking up enough text.
- **Current state:** The pipeline does not write this report by default. You can add it inside `ocr_pdf()` (e.g. collect stats in a list and write JSON at the end) or run a separate script over existing `page_*.txt` files to at least get char/word counts (see **ocr/page_stats.py**: `python -m ocr.page_stats`).

### 4.5 Script: ocr_page_stats.py

A small script **ocr/page_stats.py** (run: `python -m ocr.page_stats <dir>`) scans a directory of `page_*.txt` files and prints per-page character and word counts, and lists pages below a configurable threshold. Run it after OCR to quickly see which pages have very low yield and may need parameter tweaks or manual review.

