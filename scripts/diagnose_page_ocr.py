#!/usr/bin/env python3
"""Diagnose OCR for a single PDF page at multiple DPIs.

Saves per-DPI preprocessed images, tesseract data (mean confidence), and extracted text.

Usage:
    python scripts/diagnose_page_ocr.py --pdf data/textbook-of-modern-western-armenian.pdf \
        --page 2 --out data/textbook_ocr_improved_run_20260328_115731/diagnostics
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from hytools.ocr.preprocessor import preprocess, BinarizationMethod
from hytools.ocr.tesseract_config import build_config, TESSERACT_LANG_ARMENIAN
from PIL import Image
import csv


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--page", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--dpis", type=int, nargs="*", default=[300, 400, 600])
    p.add_argument("--psm", type=int, default=6)
    p.add_argument("--binarization", choices=["sauvola", "niblack", "otsu"], default="sauvola")
    return p.parse_args()


def run_diagnose(pdf: Path, page: int, out_dir: Path, dpis: list[int], psm: int, binarization: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for dpi in dpis:
        try:
            images = convert_from_path(str(pdf), dpi=dpi, first_page=page, last_page=page)
        except Exception as exc:
            rows.append({"dpi": dpi, "error": str(exc)})
            continue
        if not images:
            rows.append({"dpi": dpi, "error": "no image produced"})
            continue

        img = images[0]
        pre = preprocess(img, method=BinarizationMethod(binarization))

        tess_cfg = build_config(psm=psm)
        data = pytesseract.image_to_data(pre, lang=TESSERACT_LANG_ARMENIAN, config=tess_cfg, output_type=pytesseract.Output.DICT)
        confs = [c for c in data.get("conf", []) if isinstance(c, (int, float)) and c >= 0]
        mean_conf = sum(confs) / len(confs) if confs else 0
        text = pytesseract.image_to_string(pre, lang=TESSERACT_LANG_ARMENIAN, config=tess_cfg)

        # save preprocessed image for inspection
        img_path = out_dir / f"page_{page:04d}_dpi_{dpi}.png"
        if isinstance(pre, Image.Image):
            pre.save(img_path)
        else:
            # PIL expected; convert
            pre_img = Image.fromarray(pre)
            pre_img.save(img_path)

        txt_path = out_dir / f"page_{page:04d}_dpi_{dpi}.txt"
        txt_path.write_text(text, encoding="utf-8")

        rows.append({
            "dpi": dpi,
            "mean_conf": float(mean_conf),
            "char_count": len(text or ""),
            "txt": str(txt_path.name),
            "img": str(img_path.name),
        })

    # write summary CSV
    csv_path = out_dir / f"diagnose_page_{page:04d}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["dpi", "mean_conf", "char_count", "txt", "img", "error"], extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print("Wrote diagnostics to", out_dir)


if __name__ == "__main__":
    args = parse_args()
    run_diagnose(args.pdf, args.page, args.out, args.dpis, args.psm, args.binarization)
