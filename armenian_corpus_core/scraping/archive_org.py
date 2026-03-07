"""Internet Archive scraper for Armenian scanned books and periodicals.

Uses the IA Advanced Search API to catalog Armenian-language items, then
downloads their DjVuTXT (plain-text OCR output) files.  Multiple
targeted queries focus on Western Armenian content from diaspora publishers.

A catalog file (``catalog.json``) tracks all discovered items and their
download status for resume capability.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_SEARCH_API = "https://archive.org/advancedsearch.php"
_METADATA_API = "https://archive.org/metadata/{identifier}/files"
_DOWNLOAD_BASE = "https://archive.org/download/{identifier}/{filename}"
_REQUEST_DELAY = 1.0

DEFAULT_QUERIES: list[str] = [
    "language:arm AND mediatype:texts",
    "(armenian AND beirut) AND mediatype:texts",
    "(armenian AND (istanbul OR constantinople)) AND mediatype:texts",
    "(mechitarist OR mekhitarist) AND mediatype:texts",
    "(armenian AND (periodical OR journal)) AND mediatype:texts AND language:arm",
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


def search_items(queries: list[str], max_per_query: int = 500) -> dict[str, dict]:
    """Run all *queries* against the IA Advanced Search API.

    Returns a dict keyed by IA identifier, deduplicating across queries.
    """
    catalog: dict[str, dict] = {}

    for qi, query in enumerate(queries, 1):
        logger.info("IA search query %d/%d: %s", qi, len(queries), query)
        page = 1
        while True:
            params = {
                "q": query,
                "fl[]": ["identifier", "title", "language", "mediatype", "date"],
                "sort[]": "downloads desc",
                "rows": min(100, max_per_query),
                "page": page,
                "output": "json",
            }
            try:
                resp = requests.get(_SEARCH_API, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("Search API error on query %d page %d: %s", qi, page, exc)
                break

            docs = data.get("response", {}).get("docs", [])
            if not docs:
                break

            for doc in docs:
                ident = doc.get("identifier", "")
                if ident and ident not in catalog:
                    catalog[ident] = {
                        "identifier": ident,
                        "title": doc.get("title", ""),
                        "language": doc.get("language", ""),
                        "date": doc.get("date", ""),
                        "query_source": query,
                        "downloaded": False,
                        "djvu_files": [],
                    }

            fetched_total = len(catalog)
            if len(docs) < 100 or fetched_total >= max_per_query * len(queries):
                break
            page += 1
            time.sleep(_REQUEST_DELAY)

    logger.info("Cataloged %d unique items across %d queries", len(catalog), len(queries))
    return catalog


def discover_djvu_files(identifier: str) -> list[str]:
    """Query the IA Metadata API to find DjVuTXT files for an item."""
    url = _METADATA_API.format(identifier=identifier)
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        files = resp.json().get("result", [])
    except Exception as exc:
        logger.warning("Metadata API error for %s: %s", identifier, exc)
        return []

    djvu_files = []
    for f in files:
        name = f.get("name", "")
        if name.lower().endswith("_djvu.txt") or f.get("format", "").lower() == "djvutxt":
            djvu_files.append(name)
    return djvu_files


def download_file(identifier: str, filename: str, dest_dir: Path) -> Path | None:
    """Download a single file from the IA and return its path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / filename

    if out_path.exists():
        return out_path

    url = _DOWNLOAD_BASE.format(identifier=identifier, filename=filename)
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(out_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        return out_path
    except Exception as exc:
        logger.warning("Download failed %s/%s: %s", identifier, filename, exc)
        return None


def _try_wa_filter(text: str) -> bool | None:
    """Attempt WA classification; return None if classifier unavailable."""
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
    """Download DjVuTXT files for all cataloged items.

    Returns the total number of files downloaded.
    """
    total_files = 0

    for i, (ident, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded"):
            total_files += len(item.get("djvu_files", []))
            continue

        djvu_names = discover_djvu_files(ident)
        if not djvu_names:
            item["downloaded"] = True
            item["djvu_files"] = []
            if i % 50 == 0:
                _save_catalog(catalog, catalog_path)
            time.sleep(_REQUEST_DELAY)
            continue

        item_dir = dest_dir / ident
        downloaded_files = []
        for fname in djvu_names:
            path = download_file(ident, fname, item_dir)
            if path:
                if apply_wa_filter:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    result = _try_wa_filter(text)
                    if result is False:
                        logger.debug("Not WA, removing: %s/%s", ident, fname)
                        path.unlink()
                        continue

                downloaded_files.append(fname)
            time.sleep(_REQUEST_DELAY)

        item["downloaded"] = True
        item["djvu_files"] = downloaded_files
        total_files += len(downloaded_files)

        if i % 20 == 0:
            _save_catalog(catalog, catalog_path)
            logger.info(
                "Progress: %d/%d items, %d total files downloaded",
                i,
                len(catalog),
                total_files,
            )

    _save_catalog(catalog, catalog_path)
    logger.info("Download complete: %d total DjVuTXT files", total_files)
    return total_files


def run(config: dict) -> None:
    """Entry-point: catalog and download IA Armenian texts."""
    raw_dir = Path(str(config["paths"]["raw_dir"])) / "archive_org"
    scrape_cfg = config["scraping"]["archive_org"]

    queries: list[str] = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query: int = scrape_cfg.get("max_results", 500)
    apply_wa_filter: bool = scrape_cfg.get("apply_wa_filter", False)

    catalog_path = raw_dir / "catalog.json"

    catalog = _load_catalog(catalog_path)
    if not catalog:
        catalog = search_items(queries, max_per_query)
        _save_catalog(catalog, catalog_path)

    download_all(catalog, raw_dir, catalog_path, apply_wa_filter=apply_wa_filter)
