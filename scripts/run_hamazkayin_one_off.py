"""One-off Hamazkayin (Pakin) PDF crawler.

Scrapes listing pages under `/pakin-am/?cat=all-issues` (first N pages),
finds PDF links, HEAD-checks them, downloads to `data/raw/pdfs/hamazkayin_pakin`,
inserts a pending OCR record via `insert_or_skip`, then runs OCR ingest
on the downloaded directory.

Usage: run from repo root with PYTHONPATH set, e.g.:
  PYTHONPATH=. python scripts/run_hamazkayin_one_off.py --pages 4
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import yaml

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
        }
    )
    return s


def _page_urls(base: str, page: int) -> List[str]:
    if page == 1:
        return [base]
    # try a few common pagination patterns
    return [
        f"{base}&paged={page}",
        f"{base}&page={page}",
        f"{base}&pagename={page}",
        f"{base}&pg={page}",
        f"https://hamazkayin.com/pakin-am/page/{page}/?cat=all-issues",
    ]


def _find_pdf_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        href = urljoin(base_url, href)
        if href.lower().endswith(".pdf"):
            links.add(href)
    return sorted(links)


def _download_with_head(session: requests.Session, url: str, dest: Path, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        try:
            head = session.head(url, allow_redirects=True, timeout=15)
            if head.status_code == 200 and "pdf" in (head.headers.get("Content-Type") or "").lower():
                resp = session.get(url, stream=True, timeout=60)
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            fh.write(chunk)
                return True
            else:
                logger.debug("HEAD check failed (%s) for %s", head.status_code, url)
                return False
        except Exception as exc:
            logger.warning("Download attempt %d for %s failed: %s", attempt, url, exc)
            time.sleep(1 * attempt)
    return False


def main(pages: int = 4, retries: int = 3):
    cfg = {}
    cfg_path = Path("config/settings.yaml")
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    session = _make_session()
    base_listing = "https://hamazkayin.com/pakin-am/?cat=all-issues"
    found_pdfs: set[str] = set()
    for p in range(1, pages + 1):
        logger.info("Fetching listing page %d", p)
        page_ok = False
        for candidate in _page_urls(base_listing, p):
            try:
                r = session.get(candidate, timeout=20)
                if r.status_code == 200 and "html" in (r.headers.get("Content-Type") or ""):
                    logger.info("Using listing URL: %s", candidate)
                    page_ok = True
                    links = _find_pdf_links(r.text, candidate)
                    for l in links:
                        found_pdfs.add(l)
                    break
            except Exception as exc:
                logger.debug("Listing candidate failed: %s -> %s", candidate, exc)
        if not page_ok:
            logger.info("No working listing URL for page %d (continuing)", p)
        time.sleep(1.5)

    if not found_pdfs:
        logger.info("No PDF links discovered on %d pages", pages)
        return

    logger.info("Discovered %d unique PDF links", len(found_pdfs))

    # safe local directory (avoid colons on Windows)
    pdf_dir = Path("data/raw/pdfs/hamazkayin_pakin")
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # import DB helper lazily
    from hytools.ingestion._shared.helpers import insert_or_skip, open_mongodb_client

    downloaded = 0
    failed = 0
    with open_mongodb_client(cfg) as client:
        for url in sorted(found_pdfs):
            fname = url.split("/")[-1].split("?")[0]
            dest = pdf_dir / fname
            if dest.exists():
                logger.info("Already have %s — ensuring DB record", fname)
                insert_or_skip(
                    client,
                    source="hamazkayin:pakin",
                    title=fname,
                    text=None,
                    url=url,
                    metadata={"file_path": str(dest), "ocr_status": "pending", "source_type": "pdf"},
                    config=cfg,
                )
                continue

            ok = _download_with_head(session, url, dest, retries=retries)
            if not ok:
                logger.warning("Failed to download %s", url)
                failed += 1
                continue

            insert_or_skip(
                client,
                source="hamazkayin:pakin",
                title=fname,
                text=None,
                url=url,
                metadata={"file_path": str(dest), "ocr_status": "pending", "source_type": "pdf"},
                config=cfg,
            )
            downloaded += 1
            time.sleep(1.0)

    logger.info("Download complete: %d downloaded, %d failed", downloaded, failed)

    # Run OCR ingest on the downloaded dir
    try:
        from hytools.ingestion.acquisition.ocr_ingest import ingest_directory

        ocr_cfg = cfg.get("ocr", {})
        stats = ingest_directory(
            pdf_dir,
            cfg,
            source="hamazkayin:pakin",
            apply_wa_filter=True,
            dpi=ocr_cfg.get("dpi", 300),
            lang=ocr_cfg.get("tesseract_lang", "hye+eng"),
            delete_after_ingest=False,
            adaptive_dpi=ocr_cfg.get("adaptive_dpi", False),
            font_hint=ocr_cfg.get("font_hint"),
            probe_dpi=ocr_cfg.get("probe_dpi", 200),
            psm=ocr_cfg.get("psm", 3),
            confidence_threshold=ocr_cfg.get("confidence_threshold", 60),
        )
        logger.info("OCR ingest stats: %s", stats)
    except Exception as exc:
        logger.warning("OCR ingest failed: %s", exc)

    # Post-process: classify inserted documents to populate internal language tags
    try:
        from hytools.linguistics.tools.language_tagging import classify_text_to_internal_tags_detailed

        with open_mongodb_client(cfg) as client:
            if client is None:
                logger.warning("MongoDB unavailable for post-classification")
            else:
                q = {"source": "hamazkayin:pakin", "metadata.internal_language_code": {"$exists": False}}
                cursor = client.documents.find(q, {"_id": 1, "text": 1})
                updated = 0
                for doc in cursor:
                    text = (doc.get("text") or "")[:5000]
                    if not text.strip():
                        continue
                    detail = classify_text_to_internal_tags_detailed(text)
                    code = detail.get("internal_language_code")
                    branch = detail.get("internal_language_branch")
                    if code or branch:
                        update = {"metadata.internal_language_code": code, "metadata.internal_language_branch": branch}
                        try:
                            client.documents.update_one({"_id": doc["_id"]}, {"$set": update})
                            updated += 1
                        except Exception as exc:
                            logger.debug("Failed to update doc %s: %s", doc.get("_id"), exc)
                logger.info("Post-classification: updated %d documents with internal tags", updated)
    except Exception as exc:
        logger.warning("Post-classification step failed: %s", exc)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="One-off Hamazkayin Pakin PDF crawler and OCR")
    parser.add_argument("--pages", type=int, default=4, help="Number of listing pages to scan")
    parser.add_argument("--retries", type=int, default=3, help="Download retries")
    args = parser.parse_args()
    main(pages=args.pages, retries=args.retries)
