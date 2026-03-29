# OCR DPI and Resolution: In-Depth Guide

## Is Higher DPI Always Better?

**No.** Higher DPI does not always improve Tesseract accuracy. Quality is driven by **letter height in pixels**, not DPI alone.

### Key Findings from Tesseract Research

| DPI | Effect | Notes |
|-----|--------|------|
| **200 DPI** | Often optimal | Many developers report best results; avoids over-enlargement |
| **300 DPI** | Common default | Traditional recommendation; can paradoxically worsen some scripts |
| **300 vs 299** | Noticeable difference | DPI 299 produced better results than 300 on identical images (Cyrillic) |
| **400+ DPI** | Diminishing returns | Letters become very large; misrecognition (e.g. "i" → "1") increases |
| **600 DPI** | Rarely needed | Only for very small or degraded text; high memory/time cost |

### Why Higher Can Be Worse

- **Over-enlargement:** At 300–400 DPI, letters can exceed Tesseract’s ideal pixel height. The engine expects a certain character size; too large causes confusion between similar glyphs.
- **Internal scaling:** Tesseract/Leptonica may rescale internally. Feeding very high-resolution images can lead to unexpected behavior.
- **Script-specific:** Different scripts have different optimal ranges. Latin/Cyrillic may peak around 200–250 DPI; complex scripts (e.g. Devanagari) can behave differently.

### Language/Script Considerations

| Script / Language | Typical DPI Range | Notes |
|-------------------|-------------------|-------|
| **Latin (English)** | 200–300 | 200 DPI often preferred |
| **Cyrillic (Russian)** | 200–300 | Same DPI quirks as Latin; test 200 vs 300 |
| **Armenian (hye)** | 250–350 | Similar to Latin; 300 is a safe default |
| **Devanagari (Hindi)** | 300+ | Tesseract can auto-estimate; complex glyphs may need more |
| **Arabic** | 300–400 | Diacritics and connectivity may benefit from higher resolution |
| **Chinese/Japanese** | 300–400 | Dense characters; higher DPI can help |

### Recommendation for Armenian

- **Default:** 300 DPI (matches current `ocr/pipeline.py`).
- **If quality is poor:** Try 250 DPI or 275 DPI.
- **If text is very small or degraded:** Try 350–400 DPI.
- **Empirical testing:** Run a small sample at 200, 250, 300, 350 DPI and compare error rates.

### Practical Workaround

Some developers use **200 DPI** via `pixSetResolution` (C API) regardless of source DPI for consistency across scripts. For Python/pdf2image, set `dpi=200` in `convert_from_path()` and compare with 300.

---

## Dynamic DPI Selection (Armenian-Specific)

Armenian sources vary widely:
- **Tiny print** (footnotes, old books): needs higher DPI (400–600)
- **Cursive/handwritten**: long, variable strokes; may need different preprocessing more than DPI
- **Normal modern fonts**: treat like English (200–300 DPI)

### Approach: Letter-Height Targeting

Tesseract’s accuracy depends on **letter height in pixels** (20–30 px optimal). We can:

1. **Probe pass**: Render the first page at a fixed DPI (e.g. 200).
2. **Measure**: Run `image_to_data` and take the median `height` of word bounding boxes.
3. **Compute DPI**: `dpi = probe_dpi × (target_height / measured_height)` with target ≈ 25 px.
4. **Clamp**: Keep DPI in a safe range (e.g. 150–600).

### Font Hints (Config)

When automatic estimation is unreliable, use a manual hint:

| Hint   | Use case                    | DPI range   |
|--------|-----------------------------|-------------|
| `tiny` | Footnotes, dense old print   | 400–600     |
| `normal` | Modern body text           | 200–300     |
| `cursive` | Handwritten, script-like  | 300–400 + different preprocessing |

Cursive often benefits more from binarization and deskewing than from DPI changes.

**Cursive detection (implemented):** `ocr.detect_cursive: true` enables auto-detection. When `estimate_cursive_likelihood` score ≥ `cursive_threshold`, the page is re-preprocessed with cursive mode: smaller adaptive block (31), stronger denoise (5×5), morphological closing. Config: `detect_cursive`, `cursive_threshold` (default 0.5).

### Implementation

- **`ocr.pipeline`**: `adaptive_dpi`, `font_hint`, `probe_dpi` in config
- **Probe**: Renders first page at `probe_dpi`, measures median word height via Tesseract `image_to_data`
- **Formula**: `dpi = probe_dpi × (25 / measured_height)` clamped to 150–600
- **Config** (`config/settings.yaml`):

```yaml
ocr:
  dpi: 300
  adaptive_dpi: false   # Set true for auto DPI
  font_hint: null       # "tiny" | "normal" | "cursive" to override
  probe_dpi: 200
```
