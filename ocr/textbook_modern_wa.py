"""
OCR the Textbook of Modern Western Armenian PDF and save a single plain-text extract.

Uses Tesseract with hye+eng so both Armenian and English are captured (explanations,
glosses, and examples). The full extract can be fed into context for summarizing
grammar, updating docs, and improving coding logic.

Option A from docs/armenian_language_guids/TEXTBOOK_MODERN_WESTERN_ARMENIAN_GRAMMAR.md:
  Run OCR (Tesseract with Armenian + English), save output to data/textbook_modern_wa_extract.txt.

Usage:
  conda activate wa-llm
  python -m ocr.textbook_modern_wa [path/to/textbook.pdf]

Or with conda run (uses wa-llm env; Tesseract with Armenian hye is installed there):
  conda run -n wa-llm python -m ocr.textbook_modern_wa "path\\to\\textbook.pdf"

If no path is given, uses:
  - data/raw/textbook-of-modern-western-armenian.pdf (if present), or
  - Windows: %USERPROFILE%\\OneDrive\\Documents\\anki\\books\\textbook-of-modern-western-armenian.pdf

Requires: Poppler in PATH (e.g. winget install oschwartz10612.Poppler). Tesseract with Armenian (hye): use conda env wa-llm (conda install -c conda-forge tesseract); that env has tesseract 5.5.2 with hye included.
  If the script fails (e.g. "Is poppler installed and in PATH?"), install Poppler. If "tesseract is not installed", use: conda activate wa-llm (or conda install -n wa-llm -c conda-forge tesseract).

Output:
  - data/textbook_modern_wa_pages/  — per-page .txt (from ocr.pipeline)
  - data/textbook_modern_wa_extract.txt — single concatenated file (Armenian + English) for context/summarization, grammar docs, and coding logic
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root (ocr/textbook_modern_wa.py -> ocr -> repo)
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PAGES_DIR = DATA_DIR / "textbook_modern_wa_pages"
EXTRACT_FILE = DATA_DIR / "textbook_modern_wa_extract.txt"

DEFAULT_PDF_NAME = "textbook-of-modern-western-armenian.pdf"
USER_PDF = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Documents" / "anki" / "books" / DEFAULT_PDF_NAME


def find_pdf(path_arg: str | None) -> Path | None:
    if path_arg:
        p = Path(path_arg)
        return p if p.exists() else None
    if (RAW_DIR / DEFAULT_PDF_NAME).exists():
        return RAW_DIR / DEFAULT_PDF_NAME
    if USER_PDF.exists():
        return USER_PDF
    return None


def main() -> int:
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    pdf_path = find_pdf(path_arg)
    if not pdf_path:
        print("Textbook PDF not found.", file=sys.stderr)
        print("Usage: python -m ocr.textbook_modern_wa [path/to/textbook.pdf]", file=sys.stderr)
        print("Or copy the PDF to data/raw/textbook-of-modern-western-armenian.pdf", file=sys.stderr)
        return 1

    from ocr.pipeline import ocr_pdf
    from ocr.tesseract_config import TESSERACT_LANG_MIXED, PSM_BLOCK

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"OCR: {pdf_path} -> {PAGES_DIR} (lang=hye+eng, PSM={PSM_BLOCK}, confidence>=50)")
    try:
        ocr_pdf(
            pdf_path,
            PAGES_DIR,
            dpi=300,
            lang=TESSERACT_LANG_MIXED,
            adaptive_dpi=True,
            per_page_lang="hye+eng",
            psm=PSM_BLOCK,
            confidence_threshold=50,
        )
    except Exception as e:
        print(f"OCR failed: {e}", file=sys.stderr)
        return 2

    # Concatenate page files into one extract
    page_files = sorted(PAGES_DIR.glob("page_*.txt"))
    if not page_files:
        print("No page .txt files produced.", file=sys.stderr)
        return 3

    lines: list[str] = []
    for f in page_files:
        lines.append(f"\n--- Page {f.stem.replace('page_', '')} ---\n")
        lines.append(f.read_text(encoding="utf-8"))
        lines.append("")

    EXTRACT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {EXTRACT_FILE} ({len(page_files)} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
