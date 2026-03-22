"""Internet Archive scraper for Armenian scanned books and periodicals.

Uses the IA Advanced Search API to catalog Armenian-language items, then
downloads their DjVuTXT (plain-text OCR output) files.  Multiple
targeted queries focus on Western Armenian content from diaspora publishers.

A catalog file (``catalog.json``) tracks all discovered items and their
download status for resume capability.  The catalog can be refreshed,
inspected, or rebuilt via CLI subcommands.

Pipeline usage::

    python -m ingestion.runner run --only archive_org

Standalone usage::

    python -m ingestion.acquisition.archive_org run
    python -m ingestion.acquisition.archive_org catalog --status
    python -m ingestion.acquisition.archive_org catalog --refresh
    python -m ingestion.acquisition.archive_org catalog --rebuild
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from hytools.ingestion._shared.helpers import (
    compute_wa_score,
    insert_or_skip,
    is_western_armenian,
    load_catalog_from_mongodb,
    log_item,
    log_stage,
    open_mongodb_client,
    save_catalog_to_mongodb,
    WA_SCORE_THRESHOLD,
)

logger = logging.getLogger(__name__)
_STAGE = "archive_org"

_SEARCH_API = "https://archive.org/advancedsearch.php"
_METADATA_API = "https://archive.org/metadata/{identifier}/files"
_DOWNLOAD_BASE = "https://archive.org/download/{identifier}/{filename}"
_REQUEST_DELAY = 1.0
_METADATA_DELAY = 0.5
_USER_AGENT = "ArmenianCorpusCore/1.0 (Education/Research; armenian-corpus-building)"

_CATALOG_MAX_AGE_DAYS = 30

# Text file formats to look for in IA item metadata, in preference order.
# DjVuTXT is the most common for scanned books; ABBYY GZ is richer but huge;
# plain .txt is sometimes uploaded directly.
_TEXT_FORMATS: list[str] = [
    "_djvu.txt",
    "_abbyy.gz",
    ".txt",
]

# ── Exhaustive query strategy ───────────────────────────────────────────────
#
# Organized by discovery dimension to maximize recall while deduplicating
# across all queries.  IA Advanced Search uses Lucene syntax:
#   language:arm, subject:"...", creator:"...", collection:...
#
# ISO 639 codes for Armenian:
#   arm  = ISO 639-2 (bibliographic)    — most common in IA
#   hye  = ISO 639-3                    — occasionally used
#   hy   = ISO 639-1                    — rare in IA metadata
#
# All queries include mediatype:texts to exclude audio/video/software.

DEFAULT_QUERIES: list[str] = [
    # ── 1. Language-code sweep ─────────────────────────────────────────
    "language:arm AND mediatype:texts",
    "language:hye AND mediatype:texts",
    "language:hyw AND mediatype:texts",
    "language:hy AND mediatype:texts",
    'language:"Armenian" AND mediatype:texts',

    # ── 2. Subject-based ───────────────────────────────────────────────
    'subject:"Armenian language" AND mediatype:texts',
    'subject:"Western Armenian" AND mediatype:texts',
    'subject:"Eastern Armenian" AND mediatype:texts',
    'subject:"Armenian literature" AND mediatype:texts',
    'subject:"Armenian poetry" AND mediatype:texts',
    'subject:"Armenian history" AND mediatype:texts',
    'subject:"Armenian genocide" AND mediatype:texts',
    'subject:"Armenians" AND mediatype:texts',

    # ── 3. Publisher / creator organizations ───────────────────────────
    "(mechitarist OR mekhitarist OR mkhitarist) AND mediatype:texts",
    'creator:"Hamazkayin" AND mediatype:texts',
    '(creator:"AGBU" OR creator:"Armenian General Benevolent Union") AND mediatype:texts',
    'creator:"Tekeyan" AND mediatype:texts',
    '(creator:"Armenian Missionary" OR creator:"AMAA") AND mediatype:texts',
    'creator:"Catholicosate" AND mediatype:texts',

    # ── 4. Known IA collections ────────────────────────────────────────
    "collection:armenian AND mediatype:texts",
    "collection:neareasternlanguages AND language:arm AND mediatype:texts",
    'collection:"roberta" AND language:arm AND mediatype:texts',

    # ── 5. Diaspora geography ──────────────────────────────────────────
    "(armenian AND beirut) AND mediatype:texts",
    "(armenian AND aleppo) AND mediatype:texts",
    "(armenian AND cairo AND (book OR journal)) AND mediatype:texts",
    "(armenian AND (istanbul OR constantinople)) AND mediatype:texts",
    "(armenian AND jerusalem AND (book OR journal)) AND mediatype:texts",
    '(armenian AND "Buenos Aires") AND mediatype:texts',
    "(armenian AND paris AND (book OR press)) AND mediatype:texts",

    # ── 6. Periodicals and press ───────────────────────────────────────
    "(armenian AND (periodical OR journal OR newspaper OR gazette)) AND mediatype:texts AND language:arm",
    '("Zartonk" OR "Aztag" OR "Nor Gyank" OR "Baikar" OR "Aknark" OR "Arev") AND mediatype:texts',
    '("Hairenik" OR "Hayrenik" OR "Armenian Weekly") AND mediatype:texts',
    '("Arevelk" OR "Arevelk" OR "Mshak" OR "Horizon" OR "Nor Or") AND mediatype:texts',

    # ── 7. Script detection (Armenian Unicode in titles) ───────────────
    "title:(Հայ) AND mediatype:texts",
    "title:(Արմեն) AND mediatype:texts",
    "title:(Պատմ) AND mediatype:texts",
    "title:(Բառարան) AND mediatype:texts",

    # ── 8. Historical / classical ──────────────────────────────────────
    '("Grabar" OR "classical Armenian" OR "Old Armenian") AND mediatype:texts',
    '("Armenian Church" OR "Armenian Apostolic") AND mediatype:texts',
    '(armenian AND (manuscript OR codex OR palimpsest)) AND mediatype:texts',
]

# ── OCR text cleanup ────────────────────────────────────────────────────────

_RE_PAGE_MARKER = re.compile(r"^[\-_=]{3,}\s*\d*\s*[\-_=]{3,}$", re.MULTILINE)
_RE_HEADER_FOOTER = re.compile(
    r"^(?:Digitized by Google|Generated .* OCR|Internet Archive|"
    r"Universal Library|This is a digital copy).*$",
    re.MULTILINE | re.IGNORECASE,
)
_RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_RE_EXCESS_WHITESPACE = re.compile(r"\n{4,}")
_RE_EXCESS_SPACES = re.compile(r"[ \t]{3,}")


def clean_ocr_text(raw: str) -> str:
    """Clean DjVuTXT OCR output: strip page markers, headers, control chars."""
    text = raw
    text = _RE_CONTROL_CHARS.sub("", text)
    text = _RE_PAGE_MARKER.sub("", text)
    text = _RE_HEADER_FOOTER.sub("", text)
    text = _RE_EXCESS_SPACES.sub("  ", text)
    text = _RE_EXCESS_WHITESPACE.sub("\n\n\n", text)
    return text.strip()


# ── Catalog building ────────────────────────────────────────────────────────

def search_items(
    queries: list[str],
    max_per_query: int = 500,
) -> dict[str, dict]:
    """Query the IA Advanced Search API and return a catalog dict.

    Each query is paginated independently up to *max_per_query* results.
    Results are deduplicated by IA identifier across all queries.
    """
    catalog: dict[str, dict] = {}

    for qi, query in enumerate(queries, 1):
        logger.info("IA search query %d/%d: %s", qi, len(queries), query)
        page = 1
        query_count = 0
        page_size = 100

        while query_count < max_per_query:
            remaining = max_per_query - query_count
            rows = min(page_size, remaining)
            params = {
                "q": query,
                "fl[]": [
                    "identifier", "title", "language", "mediatype",
                    "date", "subject", "creator", "publisher",
                    "description", "downloads",
                ],
                "sort[]": "downloads desc",
                "rows": rows,
                "page": page,
                "output": "json",
            }
            try:
                resp = requests.get(_SEARCH_API, params=params, timeout=30, headers={"User-Agent": _USER_AGENT})
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
                        "subject": doc.get("subject", ""),
                        "creator": doc.get("creator", ""),
                        "publisher": doc.get("publisher", ""),
                        "downloads": doc.get("downloads", 0),
                        "query_source": query,
                        "downloaded": False,
                        "text_files": [],
                    }

            query_count += len(docs)
            if len(docs) < rows:
                break
            page += 1
            time.sleep(_REQUEST_DELAY)

    logger.info("Cataloged %d unique items across %d queries", len(catalog), len(queries))
    return catalog


def refresh_catalog(
    existing: dict[str, dict],
    queries: list[str],
    max_per_query: int = 500,
) -> tuple[dict[str, dict], int]:
    """Merge new IA search results into an existing catalog.

    Returns (merged_catalog, new_items_count).  Existing items keep their
    download state; only genuinely new identifiers are added.
    """
    fresh = search_items(queries, max_per_query)
    new_count = 0
    for ident, item in fresh.items():
        if ident not in existing:
            existing[ident] = item
            new_count += 1
    return existing, new_count


def _catalog_age_days(catalog_path: Path) -> float | None:
    """Return age of catalog file in days, or None if missing."""
    if not catalog_path.exists():
        return None
    mtime = datetime.fromtimestamp(catalog_path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mtime
    return age.total_seconds() / 86400


def catalog_status_mongo(client) -> None:
    """Print catalog summary from MongoDB."""
    catalog = load_catalog_from_mongodb(client, "archive_org")
    if not catalog:
        print("No catalog found (MongoDB)")
        return

    total = len(catalog)
    downloaded = sum(1 for v in catalog.values() if v.get("downloaded"))
    pending = total - downloaded
    with_files = sum(
        1 for v in catalog.values()
        if v.get("text_files") or v.get("djvu_files")
    )
    total_files = sum(
        len(v.get("text_files", v.get("djvu_files", [])))
        for v in catalog.values()
    )
    queries = {v.get("query_source", "?") for v in catalog.values()}

    by_query: dict[str, int] = {}
    for v in catalog.values():
        q = v.get("query_source", "unknown")
        by_query[q] = by_query.get(q, 0) + 1

    print("Catalog (MongoDB): archive_org")
    print(f"  Items: {total} ({downloaded} downloaded, {pending} pending)")
    print(f"  Items with text files: {with_files}")
    print(f"  Total text files tracked: {total_files}")
    print(f"  Distinct queries: {len(queries)}")
    print("  Items by query:")
    for q, cnt in sorted(by_query.items(), key=lambda x: -x[1]):
        label = q if len(q) <= 70 else q[:67] + "..."
        print(f"    {cnt:>5d}  {label}")


# ── File discovery and download ─────────────────────────────────────────────

def discover_text_files(identifier: str) -> list[str]:
    """Query the IA Metadata API to find extractable text files for an item.

    Searches for DjVuTXT (preferred), ABBYY OCR output, and plain text
    uploads.  Returns filenames in preference order.
    """
    url = _METADATA_API.format(identifier=identifier)
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        files = resp.json().get("result", [])
    except Exception as exc:
        logger.warning("Metadata API error for %s: %s", identifier, exc)
        return []

    by_priority: dict[int, list[str]] = {}
    for f in files:
        name = f.get("name", "")
        fmt = f.get("format", "").lower()
        name_lower = name.lower()

        if name_lower.endswith("_djvu.txt") or fmt == "djvutxt":
            by_priority.setdefault(0, []).append(name)
        elif name_lower.endswith(".txt") and not name_lower.endswith("_djvu.txt"):
            by_priority.setdefault(1, []).append(name)

    if not by_priority:
        return []

    best = min(by_priority.keys())
    return by_priority[best]


def _fetch_file_content(identifier: str, filename: str) -> str | None:
    """Download a single file from the IA. Returns text content or None. No file writes."""
    url = _DOWNLOAD_BASE.format(identifier=identifier, filename=filename)
    headers = {"User-Agent": _USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=120)
        # 401/403: item or file is access-restricted (e.g. borrow-only, private)
        if resp.status_code in (401, 403):
            log_item(
                logger, "warning", _STAGE, identifier, "fetch_file",
                status="access_restricted", error=f"{resp.status_code} {resp.reason}", filename=filename
            )
            return None
        resp.raise_for_status()
        content = resp.content.decode("utf-8", errors="replace")
        return content if len(content) >= 50 else None
    except requests.HTTPError as exc:
        log_item(logger, "warning", _STAGE, identifier, "fetch_file", status="error", error=str(exc), filename=filename)
        return None
    except Exception as exc:
        log_item(logger, "warning", _STAGE, identifier, "fetch_file", status="error", error=str(exc), filename=filename)
        return None


def _download_item_text(ident: str) -> tuple[str | None, list[str]]:
    """Download and combine text files for one item. Returns (combined_text, filenames). No file writes."""
    text_names = discover_text_files(ident)
    time.sleep(_METADATA_DELAY)
    if not text_names:
        return None, []

    parts: list[str] = []
    for fname in sorted(text_names):
        content = _fetch_file_content(ident, fname)
        if content:
            parts.append(content)
        time.sleep(_REQUEST_DELAY)
    combined = "\n\n".join(parts) if parts else None
    return combined, text_names


def _classify_dialect(text: str) -> str:
    """Return 'western_armenian' or 'eastern_armenian' based on WA score."""
    return "western_armenian" if is_western_armenian(text) else "eastern_armenian"


def _download_and_ingest(client, catalog: dict[str, dict], config: dict | None = None) -> dict:
    """Download text and insert directly to MongoDB. No file writes."""
    stats = {"inserted": 0, "duplicates": 0, "skipped": 0}

    for i, (ident, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded") and item.get("ingested") is not None:
            continue

        text, file_list = _download_item_text(ident)
        item["downloaded"] = True
        item["text_files"] = file_list

        if not text or len(text) < 50:
            item["ingested"] = False
            stats["skipped"] += 1
            continue

        raw = text

        text = clean_ocr_text(raw)
        if len(text) < 50:
            stats["skipped"] += 1
            continue

        # Skip documents with too few Armenian characters (e.g. English catalog pages).
        arm_chars = sum(1 for c in text if "\u0530" <= c <= "\u058F")
        if arm_chars < 30:
            logger.debug("Skipping %s: too few Armenian chars (%d)", ident, arm_chars)
            item["ingested"] = False
            stats["skipped"] += 1
            continue

        # Skip documents with significant CJK content (misclassified items).
        cjk_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3400" <= c <= "\u4dbf")
        if cjk_chars > arm_chars:
            logger.debug("Skipping %s: CJK chars (%d) exceed Armenian (%d)", ident, cjk_chars, arm_chars)
            item["ingested"] = False
            stats["skipped"] += 1
            continue

        dialect = _classify_dialect(text)
        lang_code = "hyw" if dialect == "western_armenian" else "hye" if dialect == "eastern_armenian" else "hy"

        ok = insert_or_skip(
            client,
            source="archive_org",
            title=item.get("title", ident),
            text=text,
            url=f"https://archive.org/details/{ident}",
            metadata={
                "source_type": "book",
                "identifier": ident,
                "source_language_code": lang_code,
                "publication_date": item.get("date") or None,
                "ia_date": item.get("date", ""),
                "ia_language": item.get("language", ""),
            },
            config=config,
        )
        item["ingested"] = ok
        if ok:
            stats["inserted"] += 1
            log_item(logger, "info", _STAGE, ident, "ingest", status="inserted", chars=len(text))
        else:
            stats["duplicates"] += 1

        if i % 20 == 0:
            save_catalog_to_mongodb(client, "archive_org", catalog)
            log_stage(logger, _STAGE, "progress", i=i, total=len(catalog), inserted=stats["inserted"])

    save_catalog_to_mongodb(client, "archive_org", catalog)
    return stats


# ── Pipeline entry-point ────────────────────────────────────────────────────

def run(config: dict) -> None:
    """Entry-point: catalog, download, clean, classify, ingest. MongoDB only, no JSON/txt storage."""
    config = config or {}
    scrape_cfg = config.get("scraping", {}).get("archive_org", {})
    queries = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query = scrape_cfg.get("max_results", 500)
    log_stage(logger, _STAGE, "run_start", queries=len(queries))

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        catalog = load_catalog_from_mongodb(client, "archive_org")
        if not catalog:
            log_stage(logger, _STAGE, "building_catalog")
            catalog = search_items(queries, max_per_query)
            save_catalog_to_mongodb(client, "archive_org", catalog)

        stats = _download_and_ingest(client, catalog, config)
        log_stage(logger, _STAGE, "run_complete", inserted=stats["inserted"], duplicates=stats["duplicates"], skipped=stats["skipped"])


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(
        prog="python -m ingestion.acquisition.archive_org",
        description="Internet Archive Armenian texts scraper",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the full scrape-download-ingest pipeline")
    run_p.add_argument("--config", type=Path, default=None, help="Pipeline YAML config")

    cat_p = sub.add_parser("catalog", help="Manage the IA catalog")
    cat_group = cat_p.add_mutually_exclusive_group(required=True)
    cat_group.add_argument("--status", action="store_true", help="Show catalog summary")
    cat_group.add_argument("--refresh", action="store_true",
                           help="Add new items from IA without re-downloading existing ones")
    cat_group.add_argument("--rebuild", action="store_true",
                           help="Delete and rebuild catalog from scratch (does not re-download files)")
    cat_group.add_argument("--add-queries", nargs="+", metavar="Q",
                           help="Search IA with one or more custom queries and merge results into catalog")
    cat_p.add_argument("--queries", nargs="*", default=None,
                       help="Override default search queries (for --refresh/--rebuild)")
    cat_p.add_argument("--max-per-query", type=int, default=500,
                       help="Max results per query (default: 500)")
    cat_p.add_argument("--config", type=Path, default=None)
    cat_p.add_argument("--data-dir", type=Path, default=Path("data/raw/archive_org"),
                       help="(Unused; catalogs in MongoDB only)")

    args = parser.parse_args()

    if args.command == "run":
        cfg: dict = {}
        if args.config and args.config.exists():
            import yaml
            with open(args.config, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        run(cfg)

    elif args.command == "catalog":
        cfg = {}
        if getattr(args, "config", None) and args.config and args.config.exists():
            import yaml
            with open(args.config, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        queries = args.queries or DEFAULT_QUERIES

        with open_mongodb_client(cfg) as client:
            if not client:
                print("MongoDB unavailable")
            elif args.status:
                catalog_status_mongo(client)
            elif args.refresh:
                existing = load_catalog_from_mongodb(client, "archive_org")
                merged, new_count = refresh_catalog(existing, queries, args.max_per_query)
                save_catalog_to_mongodb(client, "archive_org", merged)
                print(f"Catalog refreshed: {new_count} new items added ({len(merged)} total)")
            elif args.rebuild:
                fresh = search_items(queries, args.max_per_query)
                old = load_catalog_from_mongodb(client, "archive_org")
                for ident in fresh:
                    if ident in old and old[ident].get("downloaded"):
                        fresh[ident]["downloaded"] = True
                        fresh[ident]["text_files"] = old[ident].get("text_files", old[ident].get("djvu_files", []))
                save_catalog_to_mongodb(client, "archive_org", fresh)
                print(f"Catalog rebuilt: {len(fresh)} items")
            elif args.add_queries:
                existing = load_catalog_from_mongodb(client, "archive_org")
                merged, new_count = refresh_catalog(existing, args.add_queries, args.max_per_query)
                save_catalog_to_mongodb(client, "archive_org", merged)
                print(f"Custom queries added {new_count} new items ({len(merged)} total)")

    else:
        parser.print_help()
        sys.exit(1)
