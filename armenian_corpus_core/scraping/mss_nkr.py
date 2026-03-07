"""MSS NKR (mss.nkr.am) scraper for Armenian manuscripts and documents.

Scrapes the Nagorno-Karabakh State Archive website for PDF and image links,
then downloads them to a local directory. Uses requests + BeautifulSoup
(no JavaScript rendering required).

Output:
- Downloaded files (PDFs, images) in configurable output directory
- Catalog JSON for resume capability
"""

from __future__ import annotations

import json
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
    output_dir: str | Path = "data/raw/mss_nkr",
    catalog_path: str | Path | None = None,
    *,
    overwrite: bool = False,
    delay: float = _REQUEST_DELAY,
) -> dict[str, dict]:
    """Run the full MSS NKR scraper: discover links and download files.
    
    Parameters
    ----------
    output_dir:
        Directory to save downloaded files.
    catalog_path:
        Path to catalog JSON for resume. Default: output_dir/catalog.json
    overwrite:
        If True, re-download existing files.
    delay:
        Seconds to wait between requests.
    
    Returns
    -------
    dict
        Catalog of discovered items: {url: {status, local_path, ...}}
    """
    output_dir = Path(output_dir)
    catalog_path = Path(catalog_path or output_dir / "catalog.json")
    
    # Load existing catalog for resume
    catalog: dict[str, dict] = {}
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not load catalog: %s", exc)
    
    # Discover links
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
        
        # Save catalog periodically
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(catalog, indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
        
        if delay > 0 and i < len(links) - 1:
            time.sleep(delay)
    
    return catalog


def main() -> None:
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="python -m armenian_corpus_core.scraping.mss_nkr",
        description="Scrape MSS NKR (mss.nkr.am) for PDFs and images.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw/mss_nkr",
        help="Output directory for downloaded files",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="Catalog JSON path (default: output_dir/catalog.json)",
    )
    parser.add_argument("--overwrite", action="store_true", help="Re-download existing files")
    parser.add_argument("--delay", type=float, default=_REQUEST_DELAY, help="Delay between requests (seconds)")
    args = parser.parse_args()
    
    catalog = run_scraper(
        output_dir=args.output_dir,
        catalog_path=args.catalog,
        overwrite=args.overwrite,
        delay=args.delay,
    )
    
    n_ok = sum(1 for v in catalog.values() if v.get("status") == "downloaded")
    n_fail = sum(1 for v in catalog.values() if v.get("status") == "failed")
    print(f"Catalog: {len(catalog)} items, {n_ok} downloaded, {n_fail} failed")


if __name__ == "__main__":
    main()
