"""Library of Congress scraper for Armenian texts.

Uses the LOC JSON API to search and download Armenian-language holdings
from the Library of Congress digital collections.

Usage::
    python -m ingestion.acquisition.loc run
    python -m ingestion.acquisition.loc run --background
    python -m ingestion.acquisition.loc catalog --clean
    python -m ingestion.acquisition.loc catalog --status
    python -m ingestion.acquisition.loc status

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
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from hytool.ingestion._shared.helpers import (
    insert_or_skip,
    load_catalog_from_mongodb,
    log_item,
    log_stage,
    open_mongodb_client,
    save_catalog_to_mongodb,
    try_wa_filter,
)

logger = logging.getLogger(__name__)
_STAGE = "loc"

_SEARCH_API = "https://www.loc.gov/search/"
_ITEM_API = "https://www.loc.gov/item/{lccn}/"

# Polite scraping parameters per LOC robots.txt
_CRAWL_DELAY = 5.0
_REQUEST_DELAY = max(1.5, _CRAWL_DELAY)
_USER_AGENT = "ArmenianCorpusCore/1.0 (Education/Research; armenian-corpus-building)"
# Parallel metadata fetches (small pool to avoid 429)
_METADATA_POOL_SIZE = 3
_METADATA_BATCH_SIZE = 6

DEFAULT_QUERIES: list[str] = [
    "armenian",
    "armenia",
    "western armenian",
    "\u0570\u0561\u0575",  # հայ
]

# Broader queries for full catalog build (expand in future for more coverage)
FULL_CATALOG_QUERIES: list[str] = [
    "armenian",
    "armenia",
    "western armenian",
    "\u0570\u0561\u0575",  # հայ
    "\u0570\u0561\u0575\u0565\u0580\u0565\u0576",  # հայերեն
    "armenian language",
    "armenian literature",
    "armenian manuscript",
    "armenia history",
]

# Malformed LOC item IDs to exclude (URL fragments, invalid paths)
_INVALID_ID_PATTERNS = (
    "lccn.loc.gov",
    "cgi-bin",
    "?",
    "http",
    "www.",
    "loc.gov",
)


def _is_valid_loc_id(item_id: str) -> bool:
    """Return False if item_id is malformed (e.g. URL fragment, cgi-bin)."""
    if not item_id or len(item_id) < 5:
        return False
    lower = item_id.lower()
    if any(p in lower for p in _INVALID_ID_PATTERNS):
        return False
    # Valid LCCN: alphanumeric, may have hyphens, typically 8-12 chars
    if not re.match(r"^[a-zA-Z0-9\-_]+$", item_id):
        return False
    return True


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
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delay = (dt - now).total_seconds()
            return max(float(delay), 1.0)
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

                if not item_id or not _is_valid_loc_id(item_id):
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


def get_item_resources(
    item_id: str,
    session: requests.Session | None = None,
    error_log: list[tuple[str, int, str]] | None = None,
) -> dict | None:
    """Retrieve item metadata and resource URLs from LOC.

    If *error_log* is provided, append (item_id, status_code, message) for failures
    (503, 404, timeout, etc.) to support diagnostics.
    """
    if session is None:
        session = _get_session()

    url = _ITEM_API.format(lccn=item_id)
    params = {"fo": "json"}

    max_retries = 3
    last_status: int | None = None
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, timeout=15)
            last_status = resp.status_code

            if resp.status_code == 429:
                _adaptive_rate_limit(resp)
                continue

            if resp.status_code == 503:
                backoff = 2 ** attempt
                logger.warning("Server overloaded (503) for %s, backing off %ds", item_id, backoff)
                time.sleep(backoff)
                continue

            if resp.status_code == 404:
                msg = "Item not found (404) — may be malformed ID, moved, or restricted"
                logger.warning("%s: %s", item_id, msg)
                if error_log is not None:
                    error_log.append((item_id, 404, msg))
                return None

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
                if error_log is not None:
                    error_log.append((item_id, 0, f"timeout: {exc}"))
                return None
        except Exception as exc:
            logger.warning("Item API error for %s: %s", item_id, exc)
            if error_log is not None and last_status is not None:
                error_log.append((item_id, last_status, str(exc)))
            return None
    if error_log is not None and last_status == 503:
        error_log.append((item_id, 503, "Service unavailable after retries"))
    return None


def _fetch_metadata_batch(
    item_ids: list[str],
    error_log: list[tuple[str, int, str]],
) -> dict[str, dict | None]:
    """Fetch item metadata for multiple IDs in parallel. Returns dict item_id -> resources or None."""
    results: dict[str, dict | None] = {}
    if not item_ids:
        return results
    with ThreadPoolExecutor(max_workers=_METADATA_POOL_SIZE) as executor:
        future_to_id = {
            executor.submit(get_item_resources, iid, None, error_log): iid
            for iid in item_ids
        }
        for future in as_completed(future_to_id):
            item_id = future_to_id[future]
            try:
                results[item_id] = future.result()
            except Exception as e:
                logger.warning("Parallel metadata fetch failed for %s: %s", item_id, e)
                results[item_id] = None
    return results


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


def _fetch_text(url: str) -> str | None:
    """Download text from URL. Returns content or None. No file writes."""
    import time as _t
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            t0 = _t.perf_counter()
            resp = requests.get(url, timeout=20)
            duration_ms = (_t.perf_counter() - t0) * 1000
            resp.raise_for_status()
            text = resp.text
            if len(text) < 100:
                log_item(logger, "debug", _STAGE, url[:50], "fetch_text", status="too_short", duration_ms=duration_ms)
                return None
            log_item(logger, "debug", _STAGE, url[:50], "fetch_text", status="ok", duration_ms=duration_ms, chars=len(text))
            return text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                log_item(logger, "warning", _STAGE, url[:50], "fetch_text", status="timeout", error=str(exc))
                return None
        except Exception as exc:
            log_item(logger, "warning", _STAGE, url[:50], "fetch_text", status="error", error=str(exc))
            return None
    return None


def _download_item_text(
    item_id: str,
    item_info: dict,
    error_log: list[tuple[str, int, str]],
    pre_fetched_resources: dict | None = None,
) -> tuple[str | None, int]:
    """Download text for a single LOC item. Returns (combined_text, count). No file writes.

    If pre_fetched_resources is provided and contains item_id, that value is used
    instead of calling get_item_resources (allows parallel metadata fetch).
    """
    resources = None
    if pre_fetched_resources is not None and item_id in pre_fetched_resources:
        resources = pre_fetched_resources[item_id]
    if resources is None:
        resources = get_item_resources(item_id, error_log=error_log)
    if not resources:
        log_item(logger, "debug", _STAGE, item_id, "get_resources", status="empty")
        return None, 0

    text_urls = extract_text_from_resources(resources)
    if not text_urls:
        log_item(logger, "debug", _STAGE, item_id, "extract_urls", status="no_text_urls")
        return None, 0

    parts: list[str] = []
    for url in text_urls:
        text = _fetch_text(url)
        if text:
            parts.append(text)
        time.sleep(_REQUEST_DELAY)

    if not parts:
        return None, 0

    header = f"Title: {item_info.get('title', 'Unknown')}\nDate: {item_info.get('date', 'Unknown')}\nLOC ID: {item_id}\n\n" + "=" * 80 + "\n\n"
    combined = header + "\n\n".join(parts)
    log_item(logger, "info", _STAGE, item_id, "download", status="ok", chars=len(combined), files=len(parts))
    return combined, len(parts)


def _download_and_ingest(
    client,
    catalog: dict[str, dict],
    apply_wa_filter: bool,
    error_log_path: Path,
    config: dict | None = None,
) -> dict:
    """Download all items and insert directly to MongoDB. No file writes. Updates catalog in MongoDB."""
    stats = {"inserted": 0, "duplicates": 0, "skipped_wa": 0, "skipped_short": 0, "errors": 0}
    error_log: list[tuple[str, int, str]] = []

    to_process = [
        (item_id, item)
        for item_id, item in catalog.items()
        if not (item.get("downloaded") and item.get("ingested") is not None)
    ]
    if not to_process:
        return stats

    # Pre-fetch item metadata in parallel batches (then download text sequentially to respect rate limits)
    pre_fetched: dict[str, dict | None] = {}
    for start in range(0, len(to_process), _METADATA_BATCH_SIZE):
        batch_ids = [item_id for item_id, _ in to_process[start : start + _METADATA_BATCH_SIZE]]
        batch_results = _fetch_metadata_batch(batch_ids, error_log)
        pre_fetched.update(batch_results)
        log_stage(
            logger, _STAGE, "metadata_batch",
            batch=start // _METADATA_BATCH_SIZE + 1,
            total_batches=(len(to_process) + _METADATA_BATCH_SIZE - 1) // _METADATA_BATCH_SIZE,
        )

    for i, (item_id, item) in enumerate(to_process, 1):
        text, count = _download_item_text(
            item_id, item, error_log, pre_fetched_resources=pre_fetched
        )
        item["downloaded"] = True
        item["files_downloaded"] = count

        if not text or len(text) < 50:
            item["ingested"] = False
            stats["skipped_short"] += 1
            log_item(logger, "debug", _STAGE, item_id, "ingest", status="skipped_short")
            continue

        if apply_wa_filter:
            result = try_wa_filter(text[:5000])
            if result is False:
                item["ingested"] = False
                stats["skipped_wa"] += 1
                log_item(logger, "debug", _STAGE, item_id, "ingest", status="skipped_wa")
                continue

        ok = insert_or_skip(
            client,
            source="loc",
            title=item.get("title", item_id),
            text=text,
            url=item.get("url", f"https://www.loc.gov/item/{item_id}/"),
            metadata={
                "source_type": "library",
                "loc_id": item_id,
                "date": item.get("date", ""),
            },
            config=config,
        )
        item["ingested"] = ok
        if ok:
            stats["inserted"] += 1
        else:
            stats["duplicates"] += 1

        if i % 20 == 0:
            save_catalog_to_mongodb(client, "loc", catalog)
            log_stage(logger, _STAGE, "progress", i=i, total=len(to_process), inserted=stats["inserted"], duplicates=stats["duplicates"])

    save_catalog_to_mongodb(client, "loc", catalog)
    if error_log:
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(error_log_path, "a", encoding="utf-8") as fh:
            for eid, code, msg in error_log:
                fh.write(json.dumps({"item_id": eid, "status": code, "message": msg}) + "\n")
        log_stage(logger, _STAGE, "error_log_written", path=str(error_log_path), count=len(error_log))
    return stats


def run(config: dict) -> None:
    """Entry-point: catalog, download, and ingest LOC Armenian texts. MongoDB only, no JSON/txt storage."""
    config = config or {}
    paths = config.get("paths") or {}
    log_dir = Path(str(paths.get("log_dir", "data/logs")))
    scrape_cfg = config["scraping"]["loc"]
    queries = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query = scrape_cfg.get("max_results", 250)
    apply_wa_filter = scrape_cfg.get("apply_wa_filter", True)
    error_log_path = log_dir / "loc_api_errors.jsonl"

    log_stage(logger, _STAGE, "run_start", queries=len(queries), max_per_query=max_per_query)

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        catalog = load_catalog_from_mongodb(client, "loc")
        if not catalog:
            log_stage(logger, _STAGE, "catalog_empty_building")
            catalog = search_items(queries, max_per_query)
            n = save_catalog_to_mongodb(client, "loc", catalog)
            log_stage(logger, _STAGE, "catalog_saved", count=n)

        stats = _download_and_ingest(client, catalog, apply_wa_filter, error_log_path, config)
        log_stage(logger, _STAGE, "run_complete", inserted=stats["inserted"], duplicates=stats["duplicates"],
                  skipped_wa=stats["skipped_wa"], skipped_short=stats["skipped_short"])


# ── Status / progress monitoring ────────────────────────────────────────────

def status(log_path: Path | None = None) -> None:
    """Print LOC background download progress from the job log.

    Reads ``data/logs/loc_background_errors.log`` (or *log_path*) and shows
    progress percentage, file counts, ETA, and API error breakdown.
    """
    import re as _re

    if log_path is None:
        log_path = Path("data/logs/loc_background_errors.log")

    if not log_path.exists():
        print("No log file found - job may not have started yet")
        print(f"Expected location: {log_path.resolve()}")
        return

    content = log_path.read_text(encoding="utf-8", errors="replace")

    progress_lines = [line for line in content.split("\n") if "Progress:" in line]

    if progress_lines:
        latest = progress_lines[-1]
        print("LOC Download Progress")
        print("=" * 60)
        print(latest)

        match = _re.search(
            r"Progress: (\d+)/(\d+) items, (\d+) total files", latest
        )
        if match:
            current, total, files = (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
            percent = 100 * current / total if total else 0
            eta_hours = (total - current) * 20 / 3600
            print(f"\nProgress: {percent:.1f}% ({current}/{total} items)")
            print(f"Files downloaded: {files}")
            print(f"ETA: ~{eta_hours:.1f} hours")
    else:
        print("No progress data yet - job may still be starting")

    print("\nAPI Errors (from full log):")
    print("=" * 60)
    error_lines = [
        line
        for line in content.split("\n")
        if "[WARNING]" in line and "error" in line.lower()
    ]
    if error_lines:
        too_many = sum(1 for line in error_lines if "429" in line)
        not_found = sum(1 for line in error_lines if "404" in line)
        unavailable = sum(1 for line in error_lines if "503" in line)

        if too_many:
            print(f"  Rate limited (429): {too_many} items")
        if not_found:
            print(f"  Not found (404): {not_found} items")
        if unavailable:
            print(f"  Service unavailable (503): {unavailable} items")
        print(f"  Total errors: {len(error_lines)}")
        print("\nNote: Errors are normal - scraper retries with backoff")
    else:
        print("  (No errors yet)")


def _catalog_clean(config: dict, dry_run: bool = False) -> None:
    """Filter malformed item IDs from LOC catalog in MongoDB."""
    with open_mongodb_client(config) as client:
        if not client:
            print("MongoDB unavailable")
            return
        catalog = load_catalog_from_mongodb(client, "loc")
    total = len(catalog)
    invalid = [k for k in catalog if not _is_valid_loc_id(k)]
    valid = {k: v for k, v in catalog.items() if _is_valid_loc_id(k)}
    print(f"Catalog (MongoDB): {total} items")
    print(f"  Invalid IDs: {len(invalid)}")
    print(f"  Valid after: {len(valid)}")
    if invalid:
        print("  Sample invalid:", invalid[:10])
    if not dry_run and invalid:
        with open_mongodb_client(config) as client:
            if client:
                save_catalog_to_mongodb(client, "loc", valid)
                print("  Catalog updated in MongoDB.")
    elif dry_run:
        print("  (Dry run — no changes saved)")


def _catalog_status(config: dict) -> None:
    """Print LOC catalog summary from MongoDB."""
    with open_mongodb_client(config) as client:
        if not client:
            print("MongoDB unavailable")
            return
        catalog = load_catalog_from_mongodb(client, "loc")
    total = len(catalog)
    valid = sum(1 for k in catalog if _is_valid_loc_id(k))
    downloaded = sum(1 for v in catalog.values() if v.get("downloaded"))
    print(f"Catalog (MongoDB): {total} items ({valid} valid IDs)")
    print(f"  Downloaded: {downloaded}")


def _catalog_full(config: dict, max_per_query: int = 500) -> None:
    """Build full catalog with broader queries, save to MongoDB only."""
    catalog = search_items(FULL_CATALOG_QUERIES, max_per_query=max_per_query)
    log_stage(logger, _STAGE, "catalog_full_built", count=len(catalog))
    with open_mongodb_client(config) as client:
        if client:
            n = save_catalog_to_mongodb(client, "loc", catalog)
            print(f"Catalog saved to MongoDB: {n} items")
        else:
            print("MongoDB unavailable — catalog not saved")


if __name__ == "__main__":
    import argparse as _ap
    import subprocess as _sp
    import sys as _sys

    _parser = _ap.ArgumentParser(
        description="LOC scraper (run, status, catalog clean)",
    )
    _sub = _parser.add_subparsers(dest="command")

    _sub.add_parser("status", help="Show background download progress from log")

    _run_p = _sub.add_parser("run", help="Run the LOC scraper (requires pipeline config)")
    _run_p.add_argument("--config", type=Path, default=None, help="Pipeline YAML config")
    _run_p.add_argument(
        "--background",
        action="store_true",
        help="Spawn scraper in background (cross-platform)",
    )

    _cat_p = _sub.add_parser("catalog", help="Manage catalog (MongoDB only)")
    _cat_group = _cat_p.add_mutually_exclusive_group(required=True)
    _cat_group.add_argument("--clean", action="store_true", help="Remove malformed item IDs from MongoDB")
    _cat_group.add_argument("--status", action="store_true", help="Show catalog summary from MongoDB")
    _cat_group.add_argument("--full", action="store_true", help="Build full catalog, save to MongoDB only")
    _cat_p.add_argument("--dry-run", action="store_true", help="With --clean: report only")
    _cat_p.add_argument("--max-per-query", type=int, default=500, help="With --full: max items per query")
    _cat_p.add_argument("--config", type=Path, default=None, help="Pipeline config for MongoDB")

    _args = _parser.parse_args()

    if _args.command == "status":
        status()
    elif _args.command == "run":
        if getattr(_args, "background", False):
            _cmd = [_sys.executable, "-m", "scraping.loc", "run"]
            if _args.config and _args.config.exists():
                _cmd.extend(["--config", str(_args.config)])
            _log = Path("data/logs")
            _log.mkdir(parents=True, exist_ok=True)
            _out = open(_log / "loc_background.log", "a", encoding="utf-8")
            _err = open(_log / "loc_background_errors.log", "a", encoding="utf-8")
            _kwargs: dict = {"stdout": _out, "stderr": _err}
            import os
            if os.name != "nt":
                _kwargs["start_new_session"] = True
            _sp.Popen(_cmd, **_kwargs)
            print("LOC scraper started in background. Check: python -m ingestion.acquisition.loc status")
        else:
            cfg: dict = {}
            if _args.config and _args.config.exists():
                import yaml
                with open(_args.config, encoding="utf-8") as _fh:
                    cfg = yaml.safe_load(_fh) or {}
            run(cfg)
    elif _args.command == "catalog":
        _cat_cfg: dict = {}
        if getattr(_args, "config", None) and _args.config and _args.config.exists():
            import yaml
            with open(_args.config, encoding="utf-8") as _fh:
                _cat_cfg = yaml.safe_load(_fh) or {}
        if _args.clean:
            _catalog_clean(_cat_cfg, dry_run=_args.dry_run)
        elif _args.status:
            _catalog_status(_cat_cfg)
        elif getattr(_args, "full", False):
            _catalog_full(_cat_cfg, max_per_query=getattr(_args, "max_per_query", 500))
    else:
        _parser.print_help()
        _sys.exit(1)

