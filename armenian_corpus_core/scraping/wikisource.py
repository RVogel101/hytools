"""Armenian Wikisource scraper.

Downloads wiki-text and linked PDFs from hy.wikisource.org using the
MediaWiki API.

Supports both file-based storage and direct MongoDB insertion.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

try:
    from pymongo.errors import DuplicateKeyError  # type: ignore[reportMissingImports]
except ImportError:
    DuplicateKeyError = Exception  # placeholder when pymongo not installed

logger = logging.getLogger(__name__)

_API_BASE = "https://hy.wikisource.org/w/api.php"
_RETRY_DELAY = 2
_USER_AGENT = "ArmenianCorpusCore/1.0 (Education/Research)"
_REQUEST_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "hy,en;q=0.9",
}

_CATEGORY_PREFIX_MAP = {
    "Category:": "\u053f\u0561\u057f\u0565\u0563\u0578\u0580\u056b\u0561:",  # Կdelays:
}


def _build_session() -> requests.Session:
    """Build a configured requests session for MediaWiki API calls."""
    sess = requests.Session()
    sess.headers.update(_REQUEST_HEADERS)
    return sess


def _normalize_category_title(category: str) -> str:
    """Normalize category namespace prefix for hy.wikisource.org."""
    for src_prefix, dst_prefix in _CATEGORY_PREFIX_MAP.items():
        if category.startswith(src_prefix):
            return dst_prefix + category[len(src_prefix):]
    return category


def _api_get(session: requests.Session, params: dict, retries: int = 5) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    for attempt in range(retries):
        try:
            resp = session.get(_API_BASE, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            delay = _RETRY_DELAY * (2 ** attempt)
            logger.warning(
                "API request failed (attempt %d/%d, status=%s): %s",
                attempt + 1,
                retries,
                status,
                exc,
            )
            if attempt < retries - 1:
                time.sleep(min(delay, 30))
    raise RuntimeError(f"MediaWiki API request failed after {retries} attempts")


def iter_category_pages(session: requests.Session, category: str) -> list[str]:
    """Return all page titles in *category* (handles continuation)."""
    titles: list[str] = []
    params: dict = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": "500",
        "cmtype": "page",
    }
    while True:
        data = _api_get(session, params)
        for member in data.get("query", {}).get("categorymembers", []):
            titles.append(member["title"])
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
    return titles


def fetch_page_wikitext(session: requests.Session, title: str) -> str:
    """Return the raw wikitext for *title*."""
    data = _api_get(session, {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
    })
    pages = data.get("query", {}).get("pages", {})
    if isinstance(pages, dict):
        pages_iter = pages.values()
    else:
        pages_iter = pages
    for page in pages_iter:
        slots = page.get("revisions", [{}])[0].get("slots", {})
        main_slot = slots.get("main", {})
        return main_slot.get("content") or main_slot.get("*") or ""
    return ""


def save_page(title: str, text: str, dest_dir: Path) -> Path:
    """Write *text* to *dest_dir*/<safe_title>.txt and return the path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = title.replace("/", "_").replace(" ", "_")
    out = dest_dir / f"{safe}.txt"
    out.write_text(text, encoding="utf-8")
    return out


def save_page_to_mongodb(title: str, text: str, category: str, mongodb_client) -> bool:
    """Insert page into MongoDB. Returns True if inserted, False otherwise."""
    try:
        mongodb_client.insert_document(
            source="wikisource",
            title=title,
            text=text,
            metadata={
                "source_type": "literature",
                "category": category,
                "language_code": "hyw",
                "url": f"https://hy.wikisource.org/wiki/{title.replace(' ', '_')}",
            },
        )
        return True
    except DuplicateKeyError:
        logger.debug("Duplicate page: %s", title)
        return False
    except Exception as e:
        logger.error("Error inserting page '%s': %s", title, e)
        return False


def run(config: dict, use_mongodb: bool = False) -> None:
    """Entry-point: scrape Armenian Wikisource."""
    raw_dir = Path(config["paths"]["raw_dir"]) / "wikisource"
    categories: list[str] = config["scraping"]["wikisource"]["categories"]
    session = _build_session()

    mongodb_client = None
    if use_mongodb:
        try:
            from pymongo import MongoClient  # type: ignore[reportMissingImports]

            mongodb_uri = config.get("database", {}).get("mongodb_uri", "mongodb://localhost:27017/")
            db_name = config.get("database", {}).get("mongodb_database", "western_armenian_corpus")

            logger.info("Using MongoDB storage")
            mongodb_client = MongoClient(mongodb_uri)[db_name]
        except ImportError:
            logger.error("pymongo not installed. Run: pip install pymongo")
            logger.info("Falling back to file-based storage")
            use_mongodb = False

    stats = {"inserted": 0, "duplicates": 0, "skipped": 0}

    for category in categories:
        normalized_category = _normalize_category_title(category)
        logger.info("Processing category: %s", normalized_category)
        titles = iter_category_pages(session, normalized_category)
        logger.info("  Found %d pages", len(titles))

        if not titles:
            logger.warning(
                "  No pages found for category '%s'. Verify the title on hy.wikisource.org.",
                normalized_category,
            )
            continue

        for title in titles:
            cat_slug = normalized_category.replace("\u053f\u0561\u057f\u0565\u0563\u0578\u0580\u056b\u0561:", "").replace(" ", "_")

            if use_mongodb and mongodb_client is not None:
                existing = mongodb_client.documents.find_one(
                    {"source": "wikisource", "title": title}
                )
                if existing:
                    stats["skipped"] += 1
                    continue
            else:
                dest = raw_dir / cat_slug
                safe_title = title.replace("/", "_").replace(" ", "_")
                if (dest / f"{safe_title}.txt").exists():
                    stats["skipped"] += 1
                    continue

            text = fetch_page_wikitext(session, title)
            if not text:
                continue

            if use_mongodb and mongodb_client is not None:
                if save_page_to_mongodb(title, text, cat_slug, mongodb_client):
                    stats["inserted"] += 1
                    logger.info("  Inserted to MongoDB: %s", title)
                else:
                    stats["duplicates"] += 1
            else:
                dest = raw_dir / cat_slug
                path = save_page(title, text, dest)
                stats["inserted"] += 1
                logger.info("  Saved: %s", path)

            time.sleep(0.1)

    if use_mongodb:
        logger.info(
            "MongoDB insertion complete: %d inserted, %d duplicates, %d skipped",
            stats["inserted"],
            stats["duplicates"],
            stats["skipped"],
        )
