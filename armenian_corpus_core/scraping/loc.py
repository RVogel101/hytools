"""Library of Congress scraper for Armenian texts.

Uses the LOC JSON API to search and download Armenian-language holdings
from the Library of Congress digital collections.

Polite Scraping:
- Respects robots.txt Crawl-Delay: 5 seconds
- Reads Retry-After headers for adaptive rate limiting
- Uses connection pooling to reduce overhead
- Sets descriptive User-Agent
- Implements exponential backoff for transient errors
"""

from __future__ import annotations

import json
import logging
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_SEARCH_API = "https://www.loc.gov/search/"
_ITEM_API = "https://www.loc.gov/item/{lccn}/"

# Polite scraping parameters per LOC robots.txt
_CRAWL_DELAY = 5.0
_REQUEST_DELAY = max(1.5, _CRAWL_DELAY)
_USER_AGENT = "ArmenianCorpusCore/1.0 (Education/Research; armenian-corpus-building)"

DEFAULT_QUERIES: list[str] = [
    "armenian",
    "armenia",
    "western armenian",
    "\u0570\u0561\u0575",  # հայ
]

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    """Get or create a global requests.Session for connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        })
    return _session


def _parse_retry_after(retry_after_header: str | int | None) -> float:
    """Parse Retry-After header to get delay in seconds."""
    if retry_after_header is None:
        return _REQUEST_DELAY
    if isinstance(retry_after_header, int):
        return float(retry_after_header)
    if isinstance(retry_after_header, str):
        try:
            return float(retry_after_header)
        except ValueError:
            pass
        try:
            dt = parsedate_to_datetime(retry_after_header)
            delay = (dt - parsedate_to_datetime(dt.strftime("%a, %d %b %Y %H:%M:%S GMT"))).total_seconds()
            return max(delay, 1.0)
        except (ValueError, TypeError):
            pass
    return _REQUEST_DELAY


def _adaptive_rate_limit(resp: requests.Response) -> None:
    """Implement adaptive rate limiting based on response headers."""
    if "Retry-After" in resp.headers:
        delay = _parse_retry_after(resp.headers["Retry-After"])
        logger.info("Rate limited (429), respecting Retry-After: %ds", int(delay))
        time.sleep(delay)
        return

    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None:
        try:
            remaining_int = int(remaining)
            if remaining_int < 5:
                delay = _REQUEST_DELAY * 2
                logger.debug("Rate limit approaching (%d remaining), increasing delay to %.1fs",
                           remaining_int, delay)
                time.sleep(delay)
                return
        except ValueError:
            pass

    reset_header = resp.headers.get("X-RateLimit-Reset")
    if reset_header:
        try:
            reset_timestamp = float(reset_header)
            delay = max(reset_timestamp - time.time(), 1.0)
            logger.debug("Rate limit reset at %s, waiting %.1fs", reset_header, delay)
            time.sleep(delay)
            return
        except ValueError:
            pass

    time.sleep(_REQUEST_DELAY)


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
    max_per_query: int = 250,
) -> dict[str, dict]:
    """Search LOC catalog for Armenian texts using JSON API with connection pooling."""
    session = _get_session()
    catalog: dict[str, dict] = {}

    for qi, query in enumerate(queries, 1):
        logger.info("LOC search query %d/%d: %s", qi, len(queries), query)

        page = 1
        while True:
            params = {
                "q": query,
                "fo": "json",
                "c": 100,
                "sp": page,
                "at": "results",
            }

            max_retries = 3
            data = None
            for attempt in range(max_retries):
                try:
                    resp = session.get(_SEARCH_API, params=params, timeout=15)

                    if resp.status_code == 429:
                        _adaptive_rate_limit(resp)
                        continue

                    if resp.status_code == 503:
                        backoff = 2 ** attempt
                        logger.warning("Server overloaded (503), backing off %ds", backoff)
                        time.sleep(backoff)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    _adaptive_rate_limit(resp)
                    break

                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                    if attempt < max_retries - 1:
                        logger.warning("Connection error on query %d page %d (attempt %d/%d): %s",
                                     qi, page, attempt + 1, max_retries, exc)
                        time.sleep(1.0 * (2 ** attempt))
                    else:
                        logger.warning("Search API timeout on query %d page %d after %d attempts",
                                     qi, page, max_retries)
                except Exception as exc:
                    logger.warning("Search API error on query %d page %d: %s", qi, page, exc)
                    break

            if data is None:
                break

            results = data.get("results", [])
            if not results:
                break

            for item in results:
                item_id = None
                if "id" in item:
                    item_id = item["id"].split("/")[-2] if "/" in item["id"] else item["id"]

                if not item_id:
                    continue

                title = item.get("title", "").lower()
                description = str(item.get("description", [])).lower()
                subject = str(item.get("subject", [])).lower()

                armenian_keywords = [
                    "armenian", "armenia", "\u0570\u0561\u0575", "\u0570\u0561\u0575\u0565\u0580\u0565\u0576",
                    "\u0561\u0580\u0574\u0565\u0576", "beirut", "istanbul", "constantinople"
                ]
                has_armenian = any(
                    keyword in title or keyword in description or keyword in subject
                    for keyword in armenian_keywords
                )

                if not has_armenian:
                    continue

                if item_id not in catalog:
                    catalog[item_id] = {
                        "id": item_id,
                        "title": item.get("title", ""),
                        "date": item.get("date", ""),
                        "description": item.get("description", []),
                        "subject": item.get("subject", []),
                        "url": item.get("url", ""),
                        "query_source": query,
                        "downloaded": False,
                        "text_extracted": False,
                    }

            if len(results) < 100 or len(catalog) >= max_per_query * len(queries):
                break
            page += 1

    logger.info("Cataloged %d unique items across %d queries", len(catalog), len(queries))
    return catalog


def get_item_resources(item_id: str, session: requests.Session | None = None) -> dict | None:
    """Retrieve item metadata and resource URLs from LOC."""
    if session is None:
        session = _get_session()

    url = _ITEM_API.format(lccn=item_id)
    params = {"fo": "json"}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, timeout=15)

            if resp.status_code == 429:
                _adaptive_rate_limit(resp)
                continue

            if resp.status_code == 503:
                backoff = 2 ** attempt
                logger.warning("Server overloaded (503) for %s, backing off %ds", item_id, backoff)
                time.sleep(backoff)
                continue

            resp.raise_for_status()
            result = resp.json()
            _adaptive_rate_limit(resp)
            return result

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt < max_retries - 1:
                backoff = 1.0 * (2 ** attempt)
                logger.debug("Connection error for item %s (attempt %d/%d), waiting %.1fs: %s",
                           item_id, attempt + 1, max_retries, backoff, exc)
                time.sleep(backoff)
            else:
                logger.warning("Item API timeout for %s after %d attempts", item_id, max_retries)
                return None
        except Exception as exc:
            logger.warning("Item API error for %s: %s", item_id, exc)
            return None
    return None


def extract_text_from_resources(resources: dict) -> list[str]:
    """Extract downloadable text URLs from item resources."""
    text_urls = []

    resource_list = resources.get("resources", [])
    if not isinstance(resource_list, list):
        return text_urls

    for resource in resource_list:
        if not isinstance(resource, dict):
            continue
        files = resource.get("files", [])
        if not isinstance(files, list):
            if isinstance(files, dict):
                files = [files]
            else:
                continue

        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            file_url = file_info.get("url", "")
            mimetype = file_info.get("mimetype", "")
            if "text/plain" in mimetype or file_url.endswith(".txt"):
                text_urls.append(file_url)

    if "image_url" in resources:
        for img_url in resources.get("image_url", []):
            if img_url.endswith(".jpg") or img_url.endswith(".tif"):
                text_url = img_url.rsplit(".", 1)[0] + ".txt"
                text_urls.append(text_url)

    return text_urls


def download_text(url: str, dest_path: Path) -> bool:
    """Download text file from LOC."""
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            text = resp.text
            if len(text) < 100:
                return False
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(text, encoding="utf-8", errors="replace")
            return True
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.debug("Download timeout after %d attempts: %s", max_retries, url)
                return False
        except Exception as exc:
            logger.debug("Download failed %s: %s", url, exc)
            return False
    return False


def download_item(item_id: str, item_info: dict, dest_dir: Path) -> int:
    """Download text for a single LOC item. Returns number of text files downloaded."""
    item_dir = dest_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    resources = get_item_resources(item_id)
    if not resources:
        return 0

    text_urls = extract_text_from_resources(resources)

    files_downloaded = 0
    for i, url in enumerate(text_urls, 1):
        filename = f"text_{i:03d}.txt"
        dest_path = item_dir / filename

        if dest_path.exists():
            files_downloaded += 1
            continue

        if download_text(url, dest_path):
            files_downloaded += 1

        time.sleep(_REQUEST_DELAY)

    if files_downloaded > 0:
        combined_file = dest_dir / f"{item_id}.txt"
        with open(combined_file, "w", encoding="utf-8") as outf:
            outf.write(f"Title: {item_info.get('title', 'Unknown')}\n")
            outf.write(f"Date: {item_info.get('date', 'Unknown')}\n")
            outf.write(f"LOC ID: {item_id}\n")
            outf.write("\n" + "=" * 80 + "\n\n")
            for i in range(1, files_downloaded + 1):
                text_file = item_dir / f"text_{i:03d}.txt"
                if text_file.exists():
                    outf.write(text_file.read_text(encoding="utf-8", errors="replace"))
                    outf.write("\n\n")
        logger.info("Downloaded %s: %d text files", item_id, files_downloaded)

    return files_downloaded


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
    total_files = 0

    for i, (item_id, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded"):
            total_files += item.get("files_downloaded", 0)
            continue

        files = download_item(item_id, item, dest_dir)
        item["downloaded"] = True
        item["files_downloaded"] = files
        total_files += files

        if apply_wa_filter and files > 0:
            combined_file = dest_dir / f"{item_id}.txt"
            if combined_file.exists():
                text = combined_file.read_text(encoding="utf-8", errors="replace")
                result = _try_wa_filter(text[:5000])
                if result is False:
                    logger.debug("Not WA, removing: %s", item_id)
                    combined_file.unlink()
                    item["files_downloaded"] = 0

        if i % 20 == 0:
            _save_catalog(catalog, catalog_path)
            logger.info("Progress: %d/%d items, %d total files", i, len(catalog), total_files)

    _save_catalog(catalog, catalog_path)
    logger.info("Download complete: %d total files", total_files)
    return total_files


def run(config: dict) -> None:
    """Entry-point: catalog and download LOC Armenian texts."""
    raw_dir = Path(str(config["paths"]["raw_dir"])) / "loc"
    scrape_cfg = config["scraping"]["loc"]

    queries: list[str] = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query: int = scrape_cfg.get("max_results", 250)
    apply_wa_filter: bool = scrape_cfg.get("apply_wa_filter", True)

    catalog_path = raw_dir / "loc_catalog.json"

    catalog = _load_catalog(catalog_path)
    if not catalog:
        catalog = search_items(queries, max_per_query)
        _save_catalog(catalog, catalog_path)

    download_all(catalog, raw_dir, catalog_path, apply_wa_filter=apply_wa_filter)
