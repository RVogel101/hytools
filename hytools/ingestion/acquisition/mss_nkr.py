"""MSS NKR (mss.nkr.am) scraper for Armenian manuscripts and documents.

Scrapes the Nagorno-Karabakh State Archive website for PDF and image links,
then downloads them to a local directory. Uses requests + BeautifulSoup
(no JavaScript rendering required).

Output:
- Downloaded files (PDFs, images) in configurable output directory
- Catalog JSON for resume capability
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = "http://mss.nkr.am/"
_REQUEST_DELAY = 1.0

# File extensions to download (from armo-webscraper notebook)
_PDF_EXTENSIONS = (".pdf",)
_IMAGE_EXTENSIONS = (
    ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".gif",
    ".svg", ".psd", ".eps", ".ai", ".raw",
)
_DOC_EXTENSIONS = (".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv")
_MEDIA_EXTENSIONS = (".mp4", ".avi", ".mov", ".flv", ".mp3", ".wav")
_PRESENTATION_EXTENSIONS = (".ppt", ".pptx", ".odp", ".key")
_HTML_EXTENSIONS = (".html", ".htm")

_DOWNLOAD_EXTENSIONS = (
    _PDF_EXTENSIONS
    + _IMAGE_EXTENSIONS
    + _DOC_EXTENSIONS
    + _MEDIA_EXTENSIONS
    + _PRESENTATION_EXTENSIONS
    + _HTML_EXTENSIONS
)


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract all downloadable links from the page."""
    links: list[str] = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        path = urlparse(full_url).path.lower()
        if any(path.endswith(ext) for ext in _DOWNLOAD_EXTENSIONS):
            links.append(full_url)
    # Also check img src for images
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        full_url = urljoin(base_url, src)
        path = urlparse(full_url).path.lower()
        if any(path.endswith(ext) for ext in _IMAGE_EXTENSIONS):
            links.append(full_url)
    return list(dict.fromkeys(links))  # Deduplicate preserving order


def _filename_from_url(url: str) -> str:
    """Extract filename from URL, stripping query params."""
    path = urlparse(url).path
    name = path.split("/")[-1] or "unnamed"
    # Strip query string (e.g. ?cid=...)
    if "?" in name:
        name = name.split("?", 1)[0]
    return name


def fetch_page(url: str = _BASE_URL, timeout: int = 30) -> str:
    """Fetch the main page HTML."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def discover_links(url: str = _BASE_URL) -> list[str]:
    """Discover all downloadable links from the MSS NKR page.
    
    Returns:
        List of absolute URLs for PDFs, images, and other documents.
    """
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")
    return _extract_links(soup, url)


def download_file(
    url: str,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> Path | None:
    """Download a single file from URL to output_dir.
    
    Returns:
        Path to downloaded file, or None if skipped/failed.
    """
    filename = _filename_from_url(url)
    out_path = output_dir / filename
    
    if out_path.exists() and not overwrite:
        logger.debug("Skipping existing: %s", filename)
        return out_path
    
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        logger.info("Downloaded: %s", filename)
        return out_path
    except Exception as exc:
        logger.warning("Failed to download %s: %s", url, exc)
        return None


def run_scraper(
    output_dir: str | Path,
    client,
    *,
    overwrite: bool = False,
    delay: float = _REQUEST_DELAY,
) -> dict[str, dict]:
    """Run the full MSS NKR scraper: discover links and download files.

    Catalog is stored in MongoDB (source="mss_nkr_catalog"), not on disk.

    Parameters
    ----------
    output_dir:
        Directory to save downloaded files.
    client:
        MongoDBCorpusClient for catalog load/save.
    overwrite:
        If True, re-download existing files.
    delay:
        Seconds to wait between requests.

    Returns
    -------
    dict
        Catalog of discovered items: {url: {status, local_path, filename}}
    """
    from hytools.ingestion._shared.helpers import load_catalog_from_mongodb, save_catalog_to_mongodb

    output_dir = Path(output_dir)
    catalog_source = "mss_nkr_catalog"
    catalog = load_catalog_from_mongodb(client, catalog_source)

    logger.info("Discovering links from %s", _BASE_URL)
    links = discover_links()
    logger.info("Found %d downloadable links", len(links))

    for i, url in enumerate(links):
        if url in catalog and catalog[url].get("status") == "downloaded" and not overwrite:
            continue

        path = download_file(url, output_dir, overwrite=overwrite)
        catalog[url] = {
            "status": "downloaded" if path else "failed",
            "local_path": str(path) if path else None,
            "filename": _filename_from_url(url),
        }

        if (i + 1) % 10 == 0 or i == len(links) - 1:
            save_catalog_to_mongodb(client, catalog_source, catalog)

        if delay > 0 and i < len(links) - 1:
            time.sleep(delay)

    return catalog


def _ingest_text_files_to_mongodb(
    client,
    output_dir: Path,
    catalog: dict,
    delete_after_ingest: bool = False,
) -> dict:
    """Insert any .txt or .html files downloaded from MSS NKR into MongoDB."""
    from hytools.ingestion._shared.helpers import insert_or_skip
    from hytools.ingestion._shared.scraped_document import ScrapedDocument

    stats = {"inserted": 0, "duplicates": 0}
    for url, info in catalog.items():
        if info.get("status") != "downloaded":
            continue
        local_path = info.get("local_path")
        if not local_path:
            continue
        path = Path(local_path)
        if not path.exists():
            continue
        suffix = path.suffix.lower()
        if suffix not in (".txt", ".html", ".htm", ".csv"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) < 50:
            continue
        ok = insert_or_skip(
            client,
            doc=ScrapedDocument(
                source_family="mss_nkr",
                text=text,
                title=info.get("filename", path.name),
                source_url=url,
                source_type="archive",
                extra={"file_type": suffix.lstrip(".")},
            ),
            config=config,
        )
        if ok:
            stats["inserted"] += 1
        else:
            stats["duplicates"] += 1
        if delete_after_ingest and path.exists():
            try:
                path.unlink()
                logger.debug("Deleted after ingest: %s", path)
            except OSError as e:
                logger.warning("Could not delete %s: %s", path, e)
    return stats


def run(config: dict) -> None:
    """Entry-point: scrape and ingest MSS NKR files."""
    from hytools.ingestion._shared.helpers import open_mongodb_client

    raw_dir = Path(str(config.get("paths", {}).get("raw_dir", "data/raw"))) / "mss_nkr"
    scrape_cfg = config.get("scraping", {}).get("mss_nkr", {})
    delay = float(scrape_cfg.get("delay", _REQUEST_DELAY))
    overwrite = bool(scrape_cfg.get("overwrite", False))

    delete_after = config.get("paths", {}).get("delete_after_ingest", False)
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        catalog = run_scraper(
            output_dir=raw_dir,
            client=client,
            overwrite=overwrite,
            delay=delay,
        )
        stats = _ingest_text_files_to_mongodb(
            client, raw_dir, catalog,
            delete_after_ingest=delete_after,
            config=config,
        )
        logger.info(
            "MSS NKR MongoDB: %d inserted, %d duplicates",
            stats["inserted"], stats["duplicates"],
        )


def main() -> None:
    """CLI entry point. Requires MongoDB for catalog persistence."""
    import argparse
    from hytools.ingestion._shared.helpers import open_mongodb_client

    parser = argparse.ArgumentParser(
        prog="python -m ingestion.acquisition.mss_nkr",
        description="Scrape MSS NKR (mss.nkr.am) for PDFs and images.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw/mss_nkr",
        help="Output directory for downloaded files",
    )
    parser.add_argument("--overwrite", action="store_true", help="Re-download existing files")
    parser.add_argument("--delay", type=float, default=_REQUEST_DELAY, help="Delay between requests (seconds)")
    parser.add_argument("--config", default=None, help="Path to YAML config (optional)")
    args = parser.parse_args()

    config = {}
    if args.config:
        import yaml
        config = yaml.safe_load(open(args.config, encoding="utf-8")) or {}

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for catalog. Ensure pymongo is installed and MongoDB is running.")
        catalog = run_scraper(
            output_dir=args.output_dir,
            client=client,
            overwrite=args.overwrite,
            delay=args.delay,
        )

    n_ok = sum(1 for v in catalog.values() if v.get("status") == "downloaded")
    n_fail = sum(1 for v in catalog.values() if v.get("status") == "failed")
    print(f"Catalog: {len(catalog)} items, {n_ok} downloaded, {n_fail} failed")


if __name__ == "__main__":
    main()
