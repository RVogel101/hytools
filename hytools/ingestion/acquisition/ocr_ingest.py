"""OCR ingest pipeline: local PDF/image dirs → OCR → MongoDB with dialect tagging.

This module lives in **scraping/** (not in **ocr/**) because it orchestrates
*ingest into the corpus*: it uses ``ocr.pipeline`` and ``ocr.postprocessor``
for the actual OCR work, and ``scraping._helpers`` for MongoDB insert and
WA dialect tagging. The **ocr/** package contains only the OCR logic (PDF →
images → Tesseract → postprocess); it does not know about MongoDB or the
scraping pipeline. So this file is the bridge from local files + OCR → corpus
storage. Not redundant with ocr/.

Usage::

    python -m ingestion.acquisition.ocr_ingest run
    python -m ingestion.acquisition.ocr_ingest run --path data/raw/gomidas
    python -m ingestion.acquisition.ocr_ingest run --path /path/to/pdfs --source custom_ocr
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from hytools.ingestion._shared.helpers import insert_or_skip, open_mongodb_client, try_wa_filter

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
_PDF_EXTENSIONS = {".pdf", ".PDF"}


def _get_ocr_module():
    """Import OCR pipeline from hytools.ocr package."""
    try:
        from hytools.ocr.pipeline import ocr_pdf
        return ocr_pdf
    except ImportError as e:
        raise ImportError(
            "OCR pipeline not found. Install with OCR deps (pytesseract, pdf2image, pymongo)."
        ) from e


def _ocr_single_file(
    file_path: Path,
    output_dir: Path,
    ocr_pdf_fn,
    dpi: int = 300,
    lang: str = "hye+eng",
    adaptive_dpi: bool = False,
    font_hint: str | None = None,
    probe_dpi: int = 200,
    psm: int = 3,
    confidence_threshold: int = 60,
) -> str | None:
    """Run OCR on a single file. Returns combined text or None."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if file_path.suffix.lower() in _PDF_EXTENSIONS:
        try:
            ocr_pdf_fn(
                file_path,
                output_dir,
                dpi=dpi,
                lang=lang,
                adaptive_dpi=adaptive_dpi,
                font_hint=font_hint,
                probe_dpi=probe_dpi,
                psm=psm,
                confidence_threshold=confidence_threshold,
            )
        except Exception as exc:
            logger.warning("OCR failed for %s: %s", file_path.name, exc)
            return None
        # Combine per-page texts
        texts = []
        for p in sorted(output_dir.glob("page_*.txt")):
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
        return "\n\n".join(texts) if texts else None

    # Image-only: use pytesseract directly
    try:
        import pytesseract
        from hytools.ocr.postprocessor import postprocess
        from hytools.ocr.tesseract_config import build_config
    except ImportError:
        logger.warning("Cannot OCR image %s: missing OCR deps", file_path.name)
        return None

    try:
        from PIL import Image
        img = Image.open(file_path)
        raw = pytesseract.image_to_string(img, lang=lang, config=build_config(psm=psm))
        return postprocess(raw) if raw else None
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", file_path.name, exc)
        return None


def ingest_directory(
    dir_path: Path,
    config: dict,
    source: str = "ocr_ingest",
    apply_wa_filter: bool = True,
    dpi: int = 300,
    lang: str = "hye+eng",
    delete_after_ingest: bool = False,
    adaptive_dpi: bool = False,
    font_hint: str | None = None,
    probe_dpi: int = 200,
    psm: int = 3,
    confidence_threshold: int = 60,
) -> dict:
    """OCR all PDFs/images in directory and insert into MongoDB.

    Returns stats: {inserted, duplicates, skipped_wa, skipped_short, errors}.
    """
    import tempfile
    ocr_pdf_fn = _get_ocr_module()
    stats = {"inserted": 0, "duplicates": 0, "skipped_wa": 0, "skipped_short": 0, "errors": 0}

    files = []
    for ext in _SUPPORTED_EXTENSIONS:
        files.extend(dir_path.rglob(f"*{ext}"))

    if not files:
        logger.warning("No PDF/image files found in %s", dir_path)
        return stats

    logger.info("Found %d files to OCR in %s (MongoDB only, no file persistence)", len(files), dir_path)

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")

        for i, file_path in enumerate(files, 1):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    text = _ocr_single_file(
                        file_path, Path(tmp), ocr_pdf_fn,
                        dpi=dpi, lang=lang,
                        adaptive_dpi=adaptive_dpi, font_hint=font_hint, probe_dpi=probe_dpi,
                        psm=psm, confidence_threshold=confidence_threshold,
                    )
            except Exception as exc:
                logger.warning("OCR error for %s: %s", file_path.name, exc)
                stats["errors"] += 1
                continue

            if not text or len(text.strip()) < 50:
                stats["skipped_short"] += 1
                continue

            result = try_wa_filter(text[:5000])
            if apply_wa_filter and result is False:
                stats["skipped_wa"] += 1
                continue
            dialect = "hyw" if result is True else "hy"

            ok = insert_or_skip(
                client,
                source=source,
                title=file_path.stem,
                text=text,
                url=None,
                metadata={
                    "source_type": "ocr",
                    "file_path": str(file_path),
                    "source_language_code": dialect,
                    "ocr_dpi": dpi,
                },
                config=config,
            )
            if ok:
                stats["inserted"] += 1
            else:
                stats["duplicates"] += 1

            if delete_after_ingest and file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug("Deleted after ingest: %s", file_path)
                except OSError as e:
                    logger.warning("Could not delete %s: %s", file_path, e)

            if i % 10 == 0:
                logger.info("Progress: %d/%d", i, len(files))

    return stats


def ingest_from_gridfs(
    config: dict,
    source: str | None = None,
    apply_wa_filter: bool = True,
    dpi: int = 300,
    lang: str = "hye+eng",
    limit: int = 0,
    psm: int = 3,
    confidence_threshold: int = 60,
    adaptive_dpi: bool = False,
    font_hint: str | None = None,
    probe_dpi: int = 200,
) -> dict:
    """OCR PDFs/images from GridFS and insert text into MongoDB.

    Streams each file to a temp path, runs OCR, inserts text, deletes temp.
    Source binaries remain in GridFS as backup.

    Returns stats: {inserted, duplicates, skipped_wa, skipped_short, errors}.
    """
    import tempfile
    ocr_pdf_fn = _get_ocr_module()
    stats = {"inserted": 0, "duplicates": 0, "skipped_wa": 0, "skipped_short": 0, "errors": 0}

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")

        files = client.find_source_binaries(source=source, limit=limit)
        if not files:
            logger.warning("No source binaries found in GridFS (source=%s)", source or "any")
            return stats

        logger.info("Found %d files in GridFS to OCR", len(files))

        for i, file_meta in enumerate(files, 1):
            file_id = file_meta["_id"]
            filename = file_meta.get("filename", "unknown")
            gridfs_source = file_meta.get("source", "gridfs")
            ext = Path(filename).suffix.lower()

            if ext not in _SUPPORTED_EXTENSIONS:
                logger.debug("Skipping unsupported format: %s", filename)
                continue

            try:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp) / filename
                    client.download_source_binary_to_path(file_id, tmp_path)
                    text = _ocr_single_file(
                        tmp_path, Path(tmp), ocr_pdf_fn,
                        dpi=dpi, lang=lang,
                        adaptive_dpi=adaptive_dpi, font_hint=font_hint, probe_dpi=probe_dpi,
                        psm=psm, confidence_threshold=confidence_threshold,
                    )
            except Exception as exc:
                logger.warning("OCR error for GridFS %s: %s", filename, exc)
                stats["errors"] += 1
                continue

            if not text or len(text.strip()) < 50:
                stats["skipped_short"] += 1
                continue

            result = try_wa_filter(text[:5000])
            if apply_wa_filter and result is False:
                stats["skipped_wa"] += 1
                continue
            dialect = "hyw" if result is True else "hy"

            ok = insert_or_skip(
                client,
                source=gridfs_source,
                title=Path(filename).stem,
                text=text,
                url=None,
                metadata={
                    "source_type": "ocr",
                    "gridfs_file_id": str(file_id),
                    "source_language_code": dialect,
                    "ocr_dpi": dpi,
                },
                config=config,
            )
            if ok:
                stats["inserted"] += 1
            else:
                stats["duplicates"] += 1

            if i % 10 == 0:
                logger.info("Progress: %d/%d", i, len(files))

    return stats


def run(config: dict, path: Path | None = None, source: str = "ocr_ingest") -> None:
    """Entry-point: OCR directory and ingest to MongoDB."""
    cfg = config or {}
    if "paths" not in cfg:
        cfg.setdefault("paths", {})["raw_dir"] = "data/raw"
        cfg["paths"]["ocr_output_dir"] = "data/ocr_output"
    if "database" not in cfg:
        cfg.setdefault("database", {})["use_mongodb"] = True

    dir_path = path or Path(cfg["paths"]["raw_dir"])
    if not dir_path.exists():
        logger.error("Directory not found: %s", dir_path)
        return

    scrape_cfg = cfg.get("scraping", {}).get("ocr_ingest", {})
    ocr_cfg = cfg.get("ocr", {})
    apply_wa = scrape_cfg.get("apply_wa_filter", True)
    delete_after = cfg.get("paths", {}).get("delete_after_ingest", False)

    stats = ingest_directory(
        dir_path,
        cfg,
        source=source,
        apply_wa_filter=apply_wa,
        delete_after_ingest=delete_after,
        dpi=ocr_cfg.get("dpi", 300),
        lang=ocr_cfg.get("tesseract_lang", "hye+eng"),
        adaptive_dpi=ocr_cfg.get("adaptive_dpi", False),
        font_hint=ocr_cfg.get("font_hint"),
        probe_dpi=ocr_cfg.get("probe_dpi", 200),
        psm=ocr_cfg.get("psm", 3),
        confidence_threshold=ocr_cfg.get("confidence_threshold", 60),
    )
    logger.info(
        "OCR ingest: %d inserted, %d duplicates, %d skipped (WA), %d skipped (short), %d errors",
        stats["inserted"], stats["duplicates"], stats["skipped_wa"],
        stats["skipped_short"], stats["errors"],
    )


if __name__ == "__main__":
    import argparse
    import yaml

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="OCR local PDFs/images and ingest to MongoDB")
    parser.add_argument("--config", type=Path, help="Pipeline config YAML")
    parser.add_argument("--path", type=Path, help="Directory with PDFs/images")
    parser.add_argument("--source", default="ocr_ingest", help="MongoDB source label")
    args = parser.parse_args()

    cfg = {}
    if args.config and args.config.exists():
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    run(cfg, path=args.path, source=args.source)
