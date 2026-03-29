#!/usr/bin/env python3
"""Reprocess textbook PDF with improved OCR settings (hye+eng) and report blank pages.

Usage:

    python scripts/reprocess_textbook_ocr.py \
      --pdf data/textbook_modern_wa.pdf \
      --output data/textbook_ocr_improved \
      --dpi 350 \
      --confidence-threshold 20 \
      --per-page-lang hye+eng \
      --adaptive-dpi

This script uses the existing hytools OCR pipeline but forces mixed-language
recognition and a generous confidence threshold to reduce false blank pages.
It also outputs a summary of page coverage and blank pages found.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from textwrap import dedent
from datetime import datetime
import csv

from hytools.ocr.pipeline import ocr_pdf
from hytools.ocr.tesseract_config import TESSERACT_LANG_MIXED


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-run OCR for Western Armenian textbook PDF")
    parser.add_argument("--pdf", type=Path, required=True, help="Path to input PDF file")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for per-page text files")
    parser.add_argument("--dpi", type=int, default=400, help="Rasterization DPI (higher for quality)")
    parser.add_argument("--confidence-threshold", type=int, default=20, help="Minimum mean page confidence to keep text output")
    parser.add_argument("--adaptive-dpi", action="store_true", help="Enable adaptive DPI based on first-page script measurements")
    parser.add_argument("--font-hint", choices=["tiny", "normal", "cursive"], default=None, help="Optional DPI hint for known font size/style")
    parser.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode. 6 often works well for textbook block text.")
    parser.add_argument("--binarization", choices=["sauvola", "niblack", "otsu"], default="sauvola", help="Binarization method for preprocessor")
    parser.add_argument("--per-page-lang", choices=["off", "auto", "hye", "hye+eng", "eng"], default="hye", help="Language selection mode for each page")
    parser.add_argument("--force-overwrite", action="store_true", help="Overwrite output dir if it exists")
    parser.add_argument("--report-only", action="store_true", help="Only analyze existing OCR output files for blank pages and do not run OCR")
    return parser.parse_args()


def analyze_output(output_dir: Path) -> dict:
    stats = {
        "total_pages": 0,
        "blank_pages": 0,
        "blank_page_numbers": [],
    }

    per_page = []
    for p in sorted(output_dir.glob("page_*.txt")):
        stats["total_pages"] += 1
        text = p.read_text(encoding="utf-8", errors="replace").strip()
        page_num = int(p.stem.split("_")[-1])
        char_count = len(text)
        per_page.append({"page": page_num, "char_count": char_count, "snippet": text[:120]})
        if char_count == 0:
            stats["blank_pages"] += 1
            stats["blank_page_numbers"].append(page_num)

    stats["per_page"] = per_page
    return stats


def write_metrics_csv(stats: dict, output_dir: Path) -> None:
    csv_path = output_dir / "ocr_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["page", "char_count", "snippet"])
        for row in stats.get("per_page", []):
            writer.writerow([row["page"], row["char_count"], row["snippet"]])


def print_summary(stats: dict, output_dir: Path) -> None:
    total = stats["total_pages"]
    blank = stats["blank_pages"]
    non_blank = total - blank
    print(dedent(f"""
        OCR summary for {output_dir}
        -------------------------------
        total pages    : {total}
        non-blank pages: {non_blank}
        blank pages    : {blank}
        blank page ids : {stats['blank_page_numbers'][:30]}
        """))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    if not args.pdf.exists() or not args.pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")

    if args.report_only:
        if not args.output.exists():
            raise FileNotFoundError(f"Output directory does not exist: {args.output}")
        stats = analyze_output(args.output)
        print_summary(stats, args.output)
        return

    # If output exists and user did not request overwrite, create a timestamped directory
    if args.output.exists() and not args.force_overwrite:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{args.output.name}_run_{ts}"
        args.output = args.output.with_name(new_name)
        print(f"Output directory exists; writing to new directory: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    lang = args.per_page_lang if args.per_page_lang != "off" else TESSERACT_LANG_MIXED

    print("Running optimized OCR pass with settings:", {
        "dpi": args.dpi,
        "adaptive_dpi": args.adaptive_dpi,
        "lang": lang,
        "confidence_threshold": args.confidence_threshold,
        "psm": args.psm,
        "binarization": args.binarization,
        "font_hint": args.font_hint,
        "per_page_lang": args.per_page_lang,
    })

    ocr_pdf(
        args.pdf,
        args.output,
        dpi=args.dpi,
        lang=lang,
        binarization=args.binarization,
        confidence_threshold=args.confidence_threshold,
        adaptive_dpi=args.adaptive_dpi,
        font_hint=args.font_hint,
        probe_dpi=200,
        detect_cursive=False,
        cursive_threshold=0.5,
        per_page_lang=args.per_page_lang,
        psm=args.psm,
    )

    stats = analyze_output(args.output)
    write_metrics_csv(stats, args.output)
    print_summary(stats, args.output)

    if stats["blank_pages"] > 0:
        print("WARNING: there are blank page outputs. Consider lowering confidence threshold further or rerunning those pages with explicit 'hye+eng' and higher dpi.")


if __name__ == "__main__":
    main()
