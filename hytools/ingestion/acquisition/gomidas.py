"""Gomidas Institute newspaper scraper.

Discovers and catalogs Armenian newspaper pages from gomidas.org.
Many items are PDF/image-only — run through ocr/pipeline.py for text extraction.

Pipeline usage::

    python -m ingestion.runner run --only gomidas

Standalone::

    python -m ingestion.acquisition.gomidas run
    python -m ingestion.acquisition.gomidas catalog --status
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from hytools.ingestion._shared.helpers import (
    insert_or_skip,
    load_catalog_from_mongodb,
    log_item,
    log_stage,
    open_mongodb_client,
    save_catalog_to_mongodb,
    try_wa_filter,
)

logger = logging.getLogger(__name__)
_STAGE = "gomidas"

_BASE_URL = "https://www.gomidas.org"
_RESOURCES_URL = "https://www.gomidas.org/resources.html"
_REQUEST_DELAY = 2.0
_USER_AGENT = "ArmenianCorpusCore/1.0 (Research; armenian-corpus)"


def _discover_links(session: requests.Session) -> list[dict]:
    """Discover Armenian newspaper/document links from Gomidas resources."""
    links = []
    try:
        resp = session.get(_RESOURCES_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = str(a.get("href", "") or "")
            text = str(a.get_text() or "").strip()
            if not href or href.startswith("#"):
                continue
            combined = (href + " " + text).lower()
            if not any(kw in combined for kw in ["armenian", "armenia", "newspaper", "periodical", "journal", "pdf", "hy"]):
                continue
            full_url = href if href.startswith("http") else _BASE_URL + ("/" if not href.startswith("/") else "") + href
            links.append({"url": full_url, "title": text or full_url.split("/")[-1]})
    except Exception as exc:
        logger.warning("Gomidas discovery failed: %s", exc)
    return links


def build_catalog(max_items: int = 500) -> dict[str, dict]:
    """Build catalog of Gomidas newspaper/document links."""
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT

    links = _discover_links(session)
    catalog = {}
    for i, item in enumerate(links[:max_items]):
        key = re.sub(r"[^\w\-]", "_", item["url"])[:80]
        catalog[key] = {
            "url": item["url"],
            "title": item["title"],
            "downloaded": False,
            "format": "pdf" if ".pdf" in item["url"].lower() else "unknown",
        }
        time.sleep(_REQUEST_DELAY)
    logger.info("Gomidas catalog: %d items", len(catalog))
    return catalog


def _download_pdf_and_ocr(url: str, key: str) -> str | None:
    """Download PDF, run OCR, return combined text. Uses temp dirs only (no persistence)."""
    import tempfile
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT
    try:
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        content = resp.content
        if len(content) < 500:
            return None
    except Exception as exc:
        log_item(logger, "warning", _STAGE, key, "download", status="error", error=str(exc))
        return None

    try:
        from hytools.ocr.pipeline import ocr_pdf
    except ImportError:
        log_item(logger, "warning", _STAGE, key, "ocr", status="ocr_unavailable")
        return None

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "doc.pdf"
        pdf_path.write_bytes(content)
        out_dir = Path(tmp) / "ocr_out"
        try:
            ocr_pdf(pdf_path, out_dir)
        except Exception as exc:
            log_item(logger, "warning", _STAGE, key, "ocr", status="error", error=str(exc))
            return None
        texts = []
        for p in sorted(out_dir.glob("page_*.txt")):
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
        return "\n\n".join(texts) if texts else None


def _download_and_ingest(client, catalog: dict[str, dict], config: dict | None = None) -> dict:
    """Download PDFs, OCR, insert to MongoDB. No file persistence."""
    stats = {"inserted": 0, "duplicates": 0, "skipped": 0}
    for i, (key, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded") and item.get("ingested") is not None:
            continue
        url = item.get("url", "")
        if not url or ".pdf" not in url.lower():
            item["downloaded"] = True
            item["ingested"] = False
            stats["skipped"] += 1
            continue

        text = _download_pdf_and_ocr(url, key)
        item["downloaded"] = True
        if not text or len(text) < 50:
            item["ingested"] = False
            stats["skipped"] += 1
            time.sleep(_REQUEST_DELAY)
            continue

        if try_wa_filter(text[:5000]) is False:
            item["ingested"] = False
            stats["skipped"] += 1
            time.sleep(_REQUEST_DELAY)
            continue

        ok = insert_or_skip(
            client,
            source="gomidas",
            title=item.get("title", key),
            text=text,
            url=url,
            metadata={"source_type": "newspaper", "format": "pdf"},
            config=config,
        )
        item["ingested"] = ok
        if ok:
            stats["inserted"] += 1
            log_item(logger, "info", _STAGE, key, "ingest", status="inserted", chars=len(text))
        else:
            stats["duplicates"] += 1

        if i % 10 == 0:
            save_catalog_to_mongodb(client, "gomidas", catalog)
            log_stage(logger, _STAGE, "progress", i=i, total=len(catalog), inserted=stats["inserted"])
        time.sleep(_REQUEST_DELAY)

    save_catalog_to_mongodb(client, "gomidas", catalog)
    return stats


def run(config: dict) -> None:
    """Entry-point: discover, download, OCR, ingest. MongoDB only, no JSON/txt storage."""
    config = config or {}
    log_stage(logger, _STAGE, "run_start")

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        catalog = load_catalog_from_mongodb(client, "gomidas")
        if not catalog:
            log_stage(logger, _STAGE, "building_catalog")
            catalog = build_catalog()
            save_catalog_to_mongodb(client, "gomidas", catalog)
        stats = _download_and_ingest(client, catalog, config)
        log_stage(logger, _STAGE, "run_complete", inserted=stats["inserted"], duplicates=stats["duplicates"], skipped=stats["skipped"])


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Gomidas Institute newspaper scraper")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run discovery + download")
    cat = sub.add_parser("catalog", help="Catalog status")
    cat.add_argument("--status", action="store_true")
    cat.add_argument("--data-dir", type=Path, default=Path("data/raw/gomidas"))
    args = parser.parse_args()

    if args.command == "run":
        run({})
    elif args.command == "catalog" and args.status:
        with open_mongodb_client({}) as client:
            if client:
                c = load_catalog_from_mongodb(client, "gomidas")
                print(f"Catalog (MongoDB): {len(c)} items")
                print(f"  Downloaded: {sum(1 for v in c.values() if v.get('downloaded'))}")
    else:
        parser.print_help()
        sys.exit(1)
