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
from hytools.ocr.tesseract_config import (
    TESSERACT_LANG_ARMENIAN,
    TESSERACT_LANG_ENGLISH,
    build_config,
)
from hytools.ocr.preprocessor import preprocess, BinarizationMethod
import pytesseract
from pdf2image import convert_from_path


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
    parser.add_argument("--no-auto-detect", action="store_true", help="Disable per-page auto script-detection (force chosen --per-page-lang)")
    parser.add_argument("--force-overwrite", action="store_true", help="Overwrite output dir if it exists")
    parser.add_argument("--reprocess-missing", type=int, default=0, help="Reprocess pages with char_count < N (0 = disabled)")
    parser.add_argument("--max-attempts", type=int, default=12, help="Maximum reprocess attempts per page")
    parser.add_argument("--thresholds", type=str, default="", help="Comma-separated list of thresholds to test (e.g. 100,200,400). If empty, uses --reprocess-missing value only.")
    parser.add_argument("--use-trocr-fallback", action="store_true", help="When enabled, call TrOCR (transformers) on pages that remain below threshold after Tesseract attempts")
    parser.add_argument("--trocr-model", type=str, default="microsoft/trocr-base-printed", help="Transformers TrOCR model id to use for fallback")
    parser.add_argument("--trocr-device", type=int, default=-1, help="Device id for TrOCR (-1 = CPU, >=0 = CUDA device index)")
    parser.add_argument("--save-variants", dest="save_variants", action="store_true", help="Save per-attempt variant outputs as page_NNN_tryX.txt (for comparison)")
    parser.add_argument("--no-save-variants", dest="save_variants", action="store_false", help="Do not save per-attempt variants; overwrite standard page_NNN.txt (default: save variants)")
    parser.add_argument("--report-only", action="store_true", help="Only analyze existing OCR output files for blank pages and do not run OCR")
    parser.set_defaults(save_variants=True)
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
    pages_dir = args.output / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Determine probe language: when per-page auto-detection is enabled we
    # must pass a valid tesseract language string (not the literal 'auto').
    if args.per_page_lang == "auto":
        lang = TESSERACT_LANG_MIXED
    else:
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

    # If allowed, let pipeline auto-detect per-page language even when user
    # requested a fixed language. This helps catch pages that are actually
    # English despite a book-level preference for Armenian.
    if not args.no_auto_detect and args.per_page_lang in ("hye", "hye+eng", "eng"):
        call_per_page_lang = "auto"
        print("Per-page auto-detection enabled: pipeline will choose Armenian/English per page.")
    else:
        call_per_page_lang = args.per_page_lang

    ocr_pdf(
        args.pdf,
        pages_dir,
        dpi=args.dpi,
        lang=lang,
        binarization=args.binarization,
        confidence_threshold=args.confidence_threshold,
        adaptive_dpi=args.adaptive_dpi,
        font_hint=args.font_hint,
        probe_dpi=200,
        detect_cursive=False,
        cursive_threshold=0.5,
        per_page_lang=call_per_page_lang,
        psm=args.psm,
    )

    stats = analyze_output(pages_dir)
    write_metrics_csv(stats, args.output)
    print_summary(stats, args.output)

    if stats["blank_pages"] > 0:
        print("WARNING: there are blank page outputs. Consider lowering confidence threshold further or rerunning those pages with explicit 'hye+eng' and higher dpi.")

    # Optionally reprocess pages with low char counts
    thresholds = []
    if args.thresholds:
        thresholds = [int(x) for x in args.thresholds.split(",") if x.strip()]
    if not thresholds and args.reprocess_missing and args.reprocess_missing > 0:
        thresholds = [args.reprocess_missing]

    if thresholds:
        print(f"Reprocessing pages for thresholds={thresholds} (max_attempts={args.max_attempts})")
        summary = reprocess_low_pages(
            args.pdf,
            pages_dir,
            thresholds,
            args.max_attempts,
            args.per_page_lang,
            save_variants=args.save_variants,
            use_trocr_fallback=args.use_trocr_fallback,
            trocr_model=args.trocr_model,
            trocr_device=args.trocr_device,
        )
        # write summary CSV
        import json

        out_summary = args.output / "reprocess_threshold_summary.json"
        out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        stats = analyze_output(pages_dir)
        write_metrics_csv(stats, args.output)
        print_summary(stats, args.output)
        stats = analyze_output(pages_dir)
        write_metrics_csv(stats, args.output)
        print_summary(stats, args.output)


def _try_ocr_page(pdf_path: Path, page_num: int, dpi: int, psm: int, binarization: str, lang: str, rotation: int = 0):
    """Render a single page and OCR it. Returns (char_count, text)."""
    images = convert_from_path(str(pdf_path), dpi=dpi, first_page=page_num, last_page=page_num)
    if not images:
        return 0, ""
    image = images[0]
    if rotation:
        # rotate the PIL image (expand to avoid cropping)
        image = image.rotate(rotation, expand=True)
    pre = preprocess(image, method=BinarizationMethod(binarization))
    cfg = build_config(psm=psm)
    try:
        text = pytesseract.image_to_string(pre, lang=lang, config=cfg)
    except Exception:
        text = ""
    return len(text or ""), text


def reprocess_low_pages(
    pdf_path: Path,
    pages_dir: Path,
    thresholds: list[int],
    max_attempts: int,
    per_page_lang: str | None,
    save_variants: bool = True,
    use_trocr_fallback: bool = False,
    trocr_model: str = "microsoft/trocr-base-printed",
    trocr_device: int = -1,
) -> dict:
    """Attempt multiple OCR configs for pages below `threshold` values.

    For each threshold in `thresholds` we try a parameter sweep and save
    per-attempt variants (when `save_variants=True`) so results can be
    compared. Returns a summary dict mapping threshold -> metrics.
    """
    # Determine pages to consider (missing or below the largest threshold)
    existing = {p.stem: p for p in pages_dir.glob("page_*.txt")}
    pages_to_check = []
    for p in sorted(pages_dir.glob("page_*.txt")):
        txt = p.read_text(encoding="utf-8", errors="replace").strip()
        page_num = int(p.stem.split("_")[-1])
        pages_to_check.append((page_num, len(txt)))

    # If some pages are entirely missing (e.g., skipped), detect by scanning PDF page count
    try:
        from pdf2image import pdfinfo_from_path

        info = pdfinfo_from_path(str(pdf_path))
        total = int(info.get("Pages", 0))
    except Exception:
        total = 0
    # add missing files
    for n in range(1, total + 1):
        if not (pages_dir / f"page_{n:04d}.txt").exists():
            pages_to_check.append((n, 0))

    pages_to_check = sorted({p for p in pages_to_check})
    page_nums = [p for p, _ in pages_to_check]
    print(f"Pages to consider for reprocessing: {page_nums}")

    # Define attempt parameter space (ordered)
    dpis = [600, 400, 300]
    langs = [TESSERACT_LANG_MIXED, TESSERACT_LANG_ENGLISH, TESSERACT_LANG_ARMENIAN]
    psms = [6, 3]
    binars = ["sauvola", "otsu"]
    rotations = [0, -2, -1, 1, 2, 90, 270]

    summary: dict[int, dict] = {}

    # lazy trocr loader
    trocr_pipeline = None
    if use_trocr_fallback:
        try:
            from transformers import pipeline
            import torch

            device = trocr_device if (trocr_device >= 0 and torch.cuda.is_available()) else -1
            trocr_pipeline = pipeline("image-to-text", model=trocr_model, device=device)
        except Exception as exc:
            print("TrOCR fallback requested but transformers/torch could not be imported or initialized:", exc)
            trocr_pipeline = None

    for threshold in thresholds:
        improved = 0
        originally_below = 0
        threshold_report = []

        # pages evaluated per threshold
        for page_num, current_chars in pages_to_check:
            if current_chars >= threshold:
                continue
            originally_below += 1

            best_chars = current_chars
            best_text = (pages_dir / f"page_{page_num:04d}.txt").read_text(encoding="utf-8", errors="replace") if (pages_dir / f"page_{page_num:04d}.txt").exists() else ""
            attempt = 0

            for dpi in dpis:
                for lang in langs:
                    if per_page_lang in ("hye", "hye+eng", "eng"):
                        # allow overriding per_page_lang preference
                        lang = per_page_lang if per_page_lang != "auto" else lang
                    for psm in psms:
                        for binar in binars:
                            for rotation in rotations:
                                if attempt >= max_attempts:
                                    break
                                attempt += 1
                                chars, text = _try_ocr_page(pdf_path, page_num, dpi, psm, binar, lang, rotation=rotation)
                                if save_variants:
                                    var_file = pages_dir / f"page_{page_num:04d}_try{attempt}.txt"
                                    var_file.write_text(text or "", encoding="utf-8")
                                if chars > best_chars:
                                    best_chars = chars
                                    best_text = text
                                if best_chars >= threshold:
                                    break
                            if best_chars >= threshold or attempt >= max_attempts:
                                break
                        if best_chars >= threshold or attempt >= max_attempts:
                            break
                    if best_chars >= threshold or attempt >= max_attempts:
                        break
                if best_chars >= threshold or attempt >= max_attempts:
                    break

            # Trocr fallback attempt if enabled and still below threshold
            trocr_used = False
            if use_trocr_fallback and (best_chars < threshold) and trocr_pipeline is not None:
                try:
                    images = convert_from_path(str(pdf_path), dpi=300, first_page=page_num, last_page=page_num)
                    if images:
                        img = images[0]
                        # apply same preprocess flow for better input
                        proc_img = preprocess(img, method=BinarizationMethod("sauvola"))
                        # pipeline expects PIL image or array
                        trocr_out = trocr_pipeline(proc_img)
                        trocr_text = trocr_out[0]["generated_text"] if isinstance(trocr_out, list) and trocr_out else ""
                        attempt += 1
                        if save_variants:
                            var_file = pages_dir / f"page_{page_num:04d}_try{attempt}_trocr.txt"
                            var_file.write_text(trocr_text or "", encoding="utf-8")
                        if len(trocr_text or "") > best_chars:
                            best_chars = len(trocr_text or "")
                            best_text = trocr_text
                            trocr_used = True
                except Exception as exc:
                    print(f"TrOCR fallback failed for page {page_num}: {exc}")

            # Write chosen best_text to the canonical page file (do not overwrite if saving variants prefers keeping original - but user wants compare, so we will also keep canonical for easy reading)
            out_file = pages_dir / f"page_{page_num:04d}.txt"
            out_file.write_text(best_text or "", encoding="utf-8")

            threshold_report.append({"page": page_num, "best_chars": best_chars, "attempts": attempt, "trocr_used": trocr_used})
            if best_chars >= threshold:
                improved += 1

            print(f"Reprocessed page {page_num} (thr={threshold}): chars={best_chars} attempts={attempt} trocr={trocr_used}")

        summary[threshold] = {
            "original_below": originally_below,
            "improved_to_threshold": improved,
            "details": threshold_report,
        }

    return summary


if __name__ == "__main__":
    main()
