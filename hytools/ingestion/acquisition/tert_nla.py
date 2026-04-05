"""Scraper for tert.nla.am Bagin PDF listings.

Harvests PDF links from a Table of contents page and ingests PDFs into MongoDB
by downloading to `data/raw/pdfs/tert_nla` and creating a document record with
`ocr_status: pending` so the OCR pipeline can pick it up later.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _pdf_download_path(config: dict | None, filename: str) -> Path:
    base = (config or {}).get("storage", {}).get("pdf_dir") or Path("data/raw/pdfs")
    base = Path(base)
    dest = base / "tert_nla"
    dest.mkdir(parents=True, exist_ok=True)
    return dest / filename


def run(config: dict) -> dict:
    """Scrape the Bagin table page and ingest PDFs. Returns stats."""
    from hytools.ingestion._shared.helpers import insert_or_skip, open_mongodb_client
    from hytools.ingestion._shared.scraped_document import ScrapedDocument

    # Use pattern-driven harvesting as the primary flow (archive PDFs).
    session = requests.Session()
    # Use a browser-like User-Agent to reduce bot blocking
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    stats = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0,
             "ocr_inserted": 0, "ocr_duplicates": 0, "ocr_skipped_short": 0, "ocr_skipped_wa": 0, "ocr_errors": 0}

    # Primary: generate archive-style candidate URLs and filter with HEAD.
    links = _generate_predicted_links(config, session)
    if not links:
        logger.warning("tert_nla: no archive links found via pattern; aborting per config (no table fallback)")
        return stats

    logger.info("tert_nla: %d archive links discovered and will be processed", len(links))
    with open_mongodb_client(config) as client:
        if client is None:
            logger.warning("tert_nla: MongoDB unavailable")
            return stats
        for i, pdf_url in enumerate(links, start=1):
            stats["found"] += 1
            logger.debug("tert_nla: processing link %d/%d: %s", i, len(links), pdf_url)
            try:
                fname = pdf_url.split("/")[-1].split("?")[0]
                local_path = _pdf_download_path(config, fname)
                if not local_path.exists():
                    logger.info("tert_nla: downloading %s to %s", pdf_url, local_path)
                    try:
                        r = session.get(pdf_url, stream=True, timeout=60)
                        r.raise_for_status()
                        with open(local_path, "wb") as fh:
                            for chunk in r.iter_content(8192):
                                if chunk:
                                    fh.write(chunk)
                        stats["downloaded"] += 1
                        logger.info("tert_nla: downloaded %s", fname)
                    except Exception as exc:
                        logger.warning("tert_nla: download failed for %s: %s", pdf_url, exc)
                        stats["failed"] += 1
                        continue
                else:
                    logger.debug("tert_nla: file exists, skipping download: %s", local_path)
                    stats["skipped"] += 1

                # Run OCR on the downloaded file and insert text into MongoDB
                try:
                    from hytools.ingestion.acquisition import ocr_ingest
                    from hytools.ingestion._shared.helpers import insert_or_skip, try_wa_filter
                except Exception as exc:
                    logger.warning("tert_nla: OCR helpers unavailable: %s", exc)
                    stats["ocr_errors"] += 1
                    continue

                try:
                    import tempfile
                    ocr_fn = ocr_ingest._get_ocr_module()
                    logger.info("tert_nla: running OCR on %s", local_path)
                    with tempfile.TemporaryDirectory() as tmpdir:
                        text = ocr_ingest._ocr_single_file(
                            local_path, Path(tmpdir), ocr_fn,
                            dpi=config.get("ocr", {}).get("dpi", 300),
                            lang=config.get("ocr", {}).get("tesseract_lang", "hye+eng"),
                            adaptive_dpi=config.get("ocr", {}).get("adaptive_dpi", False),
                            font_hint=config.get("ocr", {}).get("font_hint"),
                            probe_dpi=config.get("ocr", {}).get("probe_dpi", 200),
                            psm=config.get("ocr", {}).get("psm", 3),
                            confidence_threshold=config.get("ocr", {}).get("confidence_threshold", 60),
                        )
                    logger.debug("tert_nla: OCR finished for %s (chars=%d)", fname, len(text) if text else 0)
                except Exception as exc:
                    logger.warning("tert_nla: OCR processing failed for %s: %s", local_path, exc)
                    stats["ocr_errors"] += 1
                    continue

                # Short-text filter: skip very small OCR outputs
                if not text or len(text.strip()) < 50:
                    logger.info("tert_nla: OCR output too short, skipping insert for %s (len=%d)", fname, len(text or ""))
                    stats["ocr_skipped_short"] += 1
                    continue

                # Classify text to internal language tags and add to metadata
                try:
                    from hytools.linguistics.tools.language_tagging import classify_text_to_internal_tags_detailed
                except Exception:
                    logger.debug("language_tagging module unavailable for tert_nla", exc_info=True)
                    classify_text_to_internal_tags_detailed = None

                lang_code = None
                lang_branch = None
                if classify_text_to_internal_tags_detailed:
                    try:
                        detail = classify_text_to_internal_tags_detailed(text[:5000])
                        lang_code = detail.get("internal_language_code")
                        lang_branch = detail.get("internal_language_branch")
                        logger.debug("tert_nla: language tags for %s -> %s / %s", fname, lang_code, lang_branch)
                    except Exception as exc:
                        logger.debug("tert_nla: language tagging failed for %s: %s", fname, exc)
                        lang_code = None
                        lang_branch = None

                ok = insert_or_skip(
                    client,
                    doc=ScrapedDocument(
                        source_family="tert_nla",
                        text=text,
                        title=fname,
                        source_url=pdf_url,
                        source_type="ocr",
                        internal_language_code=lang_code,
                        internal_language_branch=lang_branch,
                        extra={"file_path": str(local_path)},
                    ),
                    config=config,
                )
                if ok:
                    stats["ocr_inserted"] += 1
                    logger.info("tert_nla: inserted OCR text for %s", fname)
                else:
                    stats["ocr_duplicates"] += 1
                    logger.info("tert_nla: duplicate document skipped for %s", fname)

            except Exception as exc:
                logger.warning("tert_nla: failed %s: %s", pdf_url, exc)
                stats["failed"] += 1
    return stats


def _generate_predicted_links(config: dict | None, session: requests.Session) -> list:
    """Generate likely PDF URLs when the table page is blocked.

    Pattern observed in examples: https://tert.nla.am/archive/NLA%20AMSAGIR/Bagin/{year}/{issue}_ocr.pdf
    We try issues 1..12 for years 1962..2024 by default and a few combined-adjacent patterns.
    """
    base_template = "https://tert.nla.am/archive/NLA%20AMSAGIR/Bagin/{year}/{fname}"
    start_year = (config or {}).get("scraping", {}).get("tert_nla", {}).get("start_year", 1962)
    end_year = (config or {}).get("scraping", {}).get("tert_nla", {}).get("end_year", 2024)
    max_issue = (config or {}).get("scraping", {}).get("tert_nla", {}).get("max_issue", 12)
    candidates = []
    for year in range(start_year, end_year + 1):
        for i in range(1, max_issue + 1):
            # primary pattern: OCR file
            candidates.append(base_template.format(year=year, fname=f"{i}_ocr.pdf"))
        # adjacent combined issues: use hyphenated ranges (e.g., 4-5_ocr.pdf)
        for i in range(1, max_issue):
            candidates.append(base_template.format(year=year, fname=f"{i}-{i+1}_ocr.pdf"))

    # Persist the full list of candidates to a file for debugging/inspection
    try:
        out_dir = Path("scripts")
        out_dir.mkdir(parents=True, exist_ok=True)
        tried_path = out_dir / "tert_nla_tried_urls.txt"
        with tried_path.open("w", encoding="utf-8") as fh:
            for url in candidates:
                fh.write(url + "\n")
    except Exception:
        # best-effort only
        logger.debug("Failed to write tert_nla tried URLs list", exc_info=True)

    # Filter by HTTP HEAD to keep only existing files (lightweight check)
    found = []
    head_log_path = Path("scripts") / "tert_nla_head_results.txt"
    status_db_path = Path("scripts") / "tert_nla_url_status.json"
    # load existing status DB if present
    try:
        import json
        if status_db_path.exists():
            with status_db_path.open("r", encoding="utf-8") as fh:
                status_db = json.load(fh)
        else:
            status_db = {}
    except Exception:
        logger.debug("Failed to load tert_nla URL status DB", exc_info=True)
        status_db = {}

    import time
    import random
    import json

    for url in candidates:
        # skip rechecking recent failures (cache)
        entry = status_db.get(url)
        if entry and entry.get("status") in (403, 404) and entry.get("checked_at"):
            # if last checked within 7 days, skip
            try:
                last = float(entry.get("checked_at", 0))
                if time.time() - last < 7 * 24 * 60 * 60:
                    # record in head log and continue
                    try:
                        with head_log_path.open("a", encoding="utf-8") as fh:
                            fh.write(f"{url}\tCACHED\t{entry.get('status')}\n")
                    except Exception:
                        logger.debug("Failed to write HEAD cache log for %s", url, exc_info=True)
                    continue
            except Exception:
                logger.debug("Failed to parse cached entry for %s", url, exc_info=True)

        try:
            h = session.head(url, timeout=15, allow_redirects=True)
            status = getattr(h, "status_code", None)
            ctype = (h.headers.get("Content-Type") or "").lower()
            # If HEAD is blocked or returns 405/403, try a lightweight GET for byte range
            if status in (403, 405) or (status and status >= 400 and "pdf" in ctype) is False:
                try:
                    g = session.get(url, headers={"Range": "bytes=0-0"}, timeout=20, stream=True)
                    status = getattr(g, "status_code", None)
                    ctype = (g.headers.get("Content-Type") or "").lower()
                    g.close()
                except Exception as ge:
                    status = None
                    ctype = ""
                    # record error
                    try:
                        with head_log_path.open("a", encoding="utf-8") as fh:
                            fh.write(f"{url}\tERROR\t{ge}\n")
                    except Exception:
                        logger.debug("Failed to write HEAD error log for %s", url, exc_info=True)

            # respect Retry-After if present (simple backoff)
            retry_after = None
            try:
                retry_after = int(h.headers.get("Retry-After")) if h is not None and h.headers.get("Retry-After") else None
            except Exception:
                logger.debug("Failed to parse Retry-After header for %s", url, exc_info=True)
                retry_after = None
            if retry_after:
                time.sleep(min(retry_after, 30))

            # log
            try:
                with head_log_path.open("a", encoding="utf-8") as fh:
                    fh.write(f"{url}\t{status}\t{ctype}\n")
            except Exception:
                logger.debug("Failed to write HEAD result log for %s", url, exc_info=True)

            status_db[url] = {"status": status, "content_type": ctype, "checked_at": time.time()}
            if status == 200 and "pdf" in (ctype or "pdf"):
                found.append(url)

        except Exception as exc:
            try:
                with head_log_path.open("a", encoding="utf-8") as fh:
                    fh.write(f"{url}\tERROR\t{exc}\n")
            except Exception:
                logger.debug("Failed to write HEAD error log for %s", url, exc_info=True)
            status_db[url] = {"status": "ERROR", "error": str(exc), "checked_at": time.time()}
            # ignore network errors here; the main download loop will surface them
            # small random sleep to reduce chance of throttling
            time.sleep(0.5 + random.random())
            continue

    # persist status DB
    try:
        with status_db_path.open("w", encoding="utf-8") as fh:
            json.dump(status_db, fh, ensure_ascii=False, indent=2)
    except Exception:
        logger.debug("Failed to persist tert_nla URL status DB", exc_info=True)
    return found
    return found
