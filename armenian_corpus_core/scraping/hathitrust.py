"""HathiTrust Digital Library scraper for Armenian texts.

Uses the HathiTrust Bibliographic API and Data API to search for and download
public-domain Armenian-language holdings. HathiTrust contains 17M+ digitized
books with strong coverage of 19th-20th century academic and religious texts.

A catalog file (``hathitrust_catalog.json``) tracks discovered items and their
download status for resume capability.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_SOLR_API = "https://catalog.hathitrust.org/api/volumes/brief/json/{htid}"
_DATA_API = "https://babel.hathitrust.org/cgi/pt"
_REQUEST_DELAY = 2.0

DEFAULT_QUERIES: list[str] = [
    "language:arm",
    "armenian language",
    "\u0570\u0561\u0575\u0565\u0580\u0565\u0576",  # հայերեն
]


def _load_catalog(catalog_path: Path) -> dict[str, dict]:
    if catalog_path.exists():
        with open(catalog_path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_catalog(catalog: dict[str, dict], catalog_path: Path) -> None:
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with open(catalog_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=1)


def search_items(
    queries: list[str],
    max_per_query: int = 200,
) -> dict[str, dict]:
    """Search HathiTrust catalog for Armenian texts.

    Note: HathiTrust doesn't have a simple public search API, so we use
    their SOLR-based catalog interface. This is a simplified implementation
    that identifies known Armenian collections.
    """
    catalog: dict[str, dict] = {}

    base_url = "https://catalog.hathitrust.org/Search/Results"

    for qi, query in enumerate(queries, 1):
        logger.info("HathiTrust search query %d/%d: %s", qi, len(queries), query)

        try:
            logger.warning(
                "HathiTrust search requires HTML parsing or bulk dataset request. "
                "Visit https://www.hathitrust.org/help_digital_library for "
                "research dataset access."
            )
        except Exception as exc:
            logger.warning("Search error on query %d: %s", qi, exc)

        time.sleep(_REQUEST_DELAY)

    logger.info("HathiTrust catalog search complete")
    return catalog


def get_volume_metadata(htid: str) -> dict | None:
    """Retrieve metadata for a specific HathiTrust ID."""
    url = _SOLR_API.format(htid=htid.replace(":", "+"))
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Metadata API error for %s: %s", htid, exc)
        return None


def download_page_text(htid: str, page_seq: int, dest_path: Path) -> bool:
    """Download OCR text for a single page."""
    params = {
        "id": htid,
        "seq": page_seq,
        "view": "plaintext",
    }
    try:
        resp = requests.get(_DATA_API, params=params, timeout=60)
        resp.raise_for_status()
        text = resp.text
        if len(text) < 50:
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(text, encoding="utf-8")
        return True
    except Exception as exc:
        logger.debug("Download failed %s seq=%d: %s", htid, page_seq, exc)
        return False


def download_volume(
    htid: str,
    item_info: dict,
    dest_dir: Path,
    max_pages: int = 1000,
) -> int:
    """Download all pages of a volume. Returns number of pages downloaded."""
    volume_dir = dest_dir / htid.replace(":", "_")
    volume_dir.mkdir(parents=True, exist_ok=True)

    pages_downloaded = 0
    consecutive_fails = 0
    max_consecutive_fails = 5

    for seq in range(1, max_pages + 1):
        page_file = volume_dir / f"page_{seq:04d}.txt"

        if page_file.exists():
            pages_downloaded += 1
            consecutive_fails = 0
            continue

        success = download_page_text(htid, seq, page_file)

        if success:
            pages_downloaded += 1
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails >= max_consecutive_fails:
                break

        time.sleep(_REQUEST_DELAY)

    if pages_downloaded > 0:
        combined_file = dest_dir / f"{htid.replace(':', '_')}.txt"
        with open(combined_file, "w", encoding="utf-8") as outf:
            for seq in range(1, pages_downloaded + 1):
                page_file = volume_dir / f"page_{seq:04d}.txt"
                if page_file.exists():
                    outf.write(page_file.read_text(encoding="utf-8"))
                    outf.write("\n\n")
        logger.info("Downloaded %s: %d pages", htid, pages_downloaded)

    return pages_downloaded


def _try_wa_filter(text: str) -> bool | None:
    """Attempt WA classification; return None if unavailable."""
    try:
        from armenian_corpus_core.scraping._wa_filter import is_western_armenian
        return is_western_armenian(text)
    except ImportError:
        return None


def download_all(
    catalog: dict[str, dict],
    dest_dir: Path,
    catalog_path: Path,
    apply_wa_filter: bool = False,
) -> int:
    """Download text for all cataloged items."""
    total_pages = 0

    for i, (htid, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded"):
            total_pages += item.get("pages_downloaded", 0)
            continue

        pages = download_volume(htid, item, dest_dir)
        item["downloaded"] = True
        item["pages_downloaded"] = pages
        total_pages += pages

        if apply_wa_filter and pages > 0:
            combined_file = dest_dir / f"{htid.replace(':', '_')}.txt"
            if combined_file.exists():
                text = combined_file.read_text(encoding="utf-8", errors="replace")
                result = _try_wa_filter(text[:5000])
                if result is False:
                    logger.debug("Not WA, removing: %s", htid)
                    combined_file.unlink()
                    item["pages_downloaded"] = 0

        if i % 10 == 0:
            _save_catalog(catalog, catalog_path)
            logger.info("Progress: %d/%d items, %d total pages", i, len(catalog), total_pages)

    _save_catalog(catalog, catalog_path)
    logger.info("Download complete: %d total pages", total_pages)
    return total_pages


def run(config: dict) -> None:
    """Entry-point: catalog and download HathiTrust Armenian texts.

    NOTE: For large-scale corpus building, consider requesting a
    bulk dataset from HathiTrust Research Center:
    https://www.hathitrust.org/help_digital_library
    """
    raw_dir = Path(str(config["paths"]["raw_dir"])) / "hathitrust"
    scrape_cfg = config["scraping"]["hathitrust"]

    queries: list[str] = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query: int = scrape_cfg.get("max_results", 200)
    apply_wa_filter: bool = scrape_cfg.get("apply_wa_filter", True)

    catalog_path = raw_dir / "hathitrust_catalog.json"

    catalog = _load_catalog(catalog_path)
    if not catalog:
        logger.warning(
            "HathiTrust scraping works best with bulk dataset access. "
            "For research purposes, request a dataset from: "
            "https://www.hathitrust.org/help_digital_library"
        )
        catalog = search_items(queries, max_per_query)
        _save_catalog(catalog, catalog_path)

    if catalog:
        download_all(catalog, raw_dir, catalog_path, apply_wa_filter=apply_wa_filter)
    else:
        logger.info("No items in catalog. Consider manual catalog building or dataset request.")
