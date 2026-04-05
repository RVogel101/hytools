"""Priority A: extract text from PDF text layer when glyphs are embedded (no OCR).

Skips raster OCR for pages that already have selectable text — critical for
multi-column vector layouts where global Tesseract fails.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

UseTextLayerSetting = bool | Literal["auto"]

# Armenian + Latin letters for quality heuristic
_ARM_RE = re.compile(r"[\u0530-\u058F\uFB13-\uFB17]")
_LAT_RE = re.compile(r"[A-Za-z]")


def _has_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def extract_page_text_pymupdf(pdf_path: Path, page_num: int) -> str | None:
    """Extract UTF-8 text for one page using PyMuPDF (1-based page index).

    Returns None if PyMuPDF is not installed or extraction fails.
    """
    if not _has_pymupdf():
        return None
    import fitz

    path = Path(pdf_path)
    if not path.is_file():
        return None
    try:
        doc = fitz.open(path)
        try:
            if page_num < 1 or page_num > len(doc):
                return None
            page = doc[page_num - 1]
            return page.get_text("text") or ""
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("PyMuPDF extract failed for %s p%d: %s", path.name, page_num, exc)
        return None


def is_acceptable_text_layer(
    text: str,
    min_chars: int = 80,
    min_script_ratio: float = 0.15,
    min_newlines: int = 1,
) -> bool:
    """Return True if extracted text looks like real content, not junk/empty.

    Scanned PDFs often carry a low-quality invisible OCR text layer; single-line
    blobs that pass a short ``min_chars`` can look "acceptable" but are worse than
    raster OCR — require a bit of line structure unless the page is very text-dense.
    """
    s = (text or "").strip()
    if len(s) < min_chars:
        return False
    # One short line is usually not a full page (common bad embedded OCR / metadata).
    if s.count("\n") < min_newlines and len(s) < 400:
        return False
    letters = len(_ARM_RE.findall(s)) + len(_LAT_RE.findall(s))
    ratio = letters / max(len(s), 1)
    if ratio < min_script_ratio:
        return False
    # Reject mostly replacement chars / control noise
    bad = sum(1 for c in s if ord(c) < 32 and c not in "\n\t\r")
    if bad / max(len(s), 1) > 0.05:
        return False
    return True


def try_text_layer_page(pdf_path: Path, page_num: int, **kwargs: Any) -> str | None:
    """Extract page text; return string if acceptable, else None."""
    raw = extract_page_text_pymupdf(pdf_path, page_num)
    if raw is None:
        return None
    if not is_acceptable_text_layer(raw, **kwargs):
        logger.debug("Text layer for page %d rejected by heuristic (len=%d)", page_num, len(raw.strip()))
        return None
    logger.info("Using PDF text layer for %s page %d (%d chars)", pdf_path.name, page_num, len(raw.strip()))
    return raw


def parse_use_text_layer_setting(raw: Any) -> UseTextLayerSetting:
    """Normalize YAML/CLI values to ``True`` / ``False`` / ``\"auto\"``."""
    if raw is True or raw is False:
        return raw
    if raw is None:
        return False
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("auto", "detect", "guess"):
            return "auto"
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off", ""):
            return False
    return False


def _sample_page_indices(n_pages: int, max_sample: int = 5) -> list[int]:
    """Spread indices across the document (not only the first pages)."""
    if n_pages <= 0:
        return []
    m = min(max_sample, n_pages)
    if m == 1:
        return [0]
    return sorted({int(round(i * (n_pages - 1) / (m - 1))) for i in range(m)})


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    mid = len(s) // 2
    if len(s) % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def _page_image_dominant(page: Any) -> bool:
    """Heuristic: scanned page as full-page image with almost no vector text."""
    try:
        d = page.get_text("dict") or {}
        blocks = d.get("blocks") or []
        text_area = 0.0
        img_area = 0.0
        for b in blocks:
            if b.get("type") == 0:
                for line in b.get("lines") or []:
                    for sp in line.get("spans") or []:
                        bb = sp.get("bbox")
                        if bb and len(bb) >= 4:
                            text_area += max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])
            elif b.get("type") == 1:
                bb = b.get("bbox")
                if bb and len(bb) >= 4:
                    img_area += max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])
        r = page.rect
        page_area = max(r.width * r.height, 1.0)
        return (img_area / page_area) > 0.55 and (text_area / page_area) < 0.03
    except Exception:
        logger.debug("Image-dominant probe failed for page", exc_info=True)
        return False


def recommend_text_layer_from_probe_stats(
    *,
    acceptable_count: int,
    image_dominant_count: int,
    sampled: int,
    median_chars_acceptable: float,
    median_newlines_acceptable: float,
) -> tuple[bool, str]:
    """Pure decision used by :func:`probe_text_layer_policy` (testable without a PDF)."""
    if sampled <= 0:
        return False, "no pages sampled"

    usable = sampled - image_dominant_count
    if usable <= 0:
        return False, "sampled pages look image-dominant (scanned bitmaps)"

    ratio = acceptable_count / usable
    # Need most pages to pass the same per-page bar we use when text layer is on.
    if ratio < 0.5:
        return (
            False,
            f"only {acceptable_count}/{usable} non-image pages pass text-layer quality ({ratio:.0%} < 50%)",
        )

    if median_chars_acceptable < 120:
        return (
            False,
            f"median chars on acceptable pages ({median_chars_acceptable:.0f}) < 120 — likely thin OCR layer",
        )

    if median_newlines_acceptable < 1.0 and median_chars_acceptable < 500:
        return (
            False,
            "little line structure in embedded text — prefer raster OCR",
        )

    return (
        True,
        f"{acceptable_count}/{usable} sampled pages pass heuristics (median {median_chars_acceptable:.0f} chars, "
        f"{median_newlines_acceptable:.1f} newlines)",
    )


@dataclass(frozen=True)
class TextLayerProbeResult:
    recommend: bool
    reason: str
    pages_sampled: int
    acceptable_pages: int
    image_dominant_pages: int
    median_chars_acceptable: float
    median_newlines_acceptable: float


def probe_text_layer_policy(
    pdf_path: Path,
    *,
    max_sample: int = 5,
) -> TextLayerProbeResult:
    """Decide if embedded text is likely reliable (born-digital–like) vs scanned junk.

    Samples pages across the whole PDF, applies :func:`is_acceptable_text_layer` and
    image-dominance checks. **Heuristic only** — verify on a few pages when quality is critical.

    Returns
    -------
    TextLayerProbeResult
        ``recommend`` is whether to set ``use_text_layer`` to True for this file.
    """
    path = Path(pdf_path)
    if not _has_pymupdf() or not path.is_file():
        return TextLayerProbeResult(
            recommend=False,
            reason="PyMuPDF not installed or file missing",
            pages_sampled=0,
            acceptable_pages=0,
            image_dominant_pages=0,
            median_chars_acceptable=0.0,
            median_newlines_acceptable=0.0,
        )

    import fitz

    try:
        doc = fitz.open(path)
    except Exception as exc:
        logger.debug("probe_text_layer_policy open failed: %s", exc)
        return TextLayerProbeResult(
            recommend=False,
            reason=f"could not open PDF: {exc}",
            pages_sampled=0,
            acceptable_pages=0,
            image_dominant_pages=0,
            median_chars_acceptable=0.0,
            median_newlines_acceptable=0.0,
        )

    try:
        n = len(doc)
        indices = _sample_page_indices(n, max_sample=max_sample)
        acceptable_chars: list[float] = []
        acceptable_newlines: list[float] = []
        acceptable = 0
        img_dom = 0

        for i in indices:
            page = doc[i]
            if _page_image_dominant(page):
                img_dom += 1
                continue
            text = page.get_text("text") or ""
            st = text.strip()
            if is_acceptable_text_layer(text):
                acceptable += 1
                acceptable_chars.append(float(len(st)))
                acceptable_newlines.append(float(st.count("\n")))

        med_c = _median(acceptable_chars)
        med_n = _median(acceptable_newlines)
        usable = len(indices) - img_dom
        rec, reason = recommend_text_layer_from_probe_stats(
            acceptable_count=acceptable,
            image_dominant_count=img_dom,
            sampled=len(indices),
            median_chars_acceptable=med_c,
            median_newlines_acceptable=med_n,
        )
        return TextLayerProbeResult(
            recommend=rec,
            reason=reason,
            pages_sampled=len(indices),
            acceptable_pages=acceptable,
            image_dominant_pages=img_dom,
            median_chars_acceptable=med_c,
            median_newlines_acceptable=med_n,
        )
    finally:
        doc.close()
