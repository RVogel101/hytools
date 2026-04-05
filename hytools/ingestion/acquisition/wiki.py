"""Unified Wiki scrapers: Wikipedia (WA/EA) and Wikisource.

- **Wikipedia**: Download XML dumps from dumps.wikimedia.org (hyw or hy),
  stream bz2, extract articles with shared wikitext cleanup, insert into MongoDB.
- **Wikisource**: Fetch pages from hy.wikisource.org via MediaWiki API by category,
  clean wikitext, classify dialect (WA score), insert into MongoDB.

Runner entry points (single module scraping.wiki):
  run_wikipedia(config)  — WA and/or EA based on config (scraping.wikipedia.*, scraping.eastern_armenian.enabled)
  run_wikisource(config) — Armenian Wikisource by category
"""
from __future__ import annotations

import bz2
import logging
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

from hytools.ingestion._shared.helpers import (
    clean_wikitext,
    compute_wa_score,
    download_dump,
    insert_or_skip,
    is_redirect,
    open_mongodb_client,
    resolve_dump_date,
    WA_SCORE_THRESHOLD,
)
from hytools.ingestion._shared.scraped_document import ScrapedDocument

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
#  Wikipedia (dump-based)
# -----------------------------------------------------------------------------

def extract_wikipedia_to_mongodb(
    dump_path: Path,
    mongodb_client,
    *,
    source: str,
    language_code: str,
    dump_file_name: Optional[str] = None,
    config: Optional[dict] = None,
) -> dict:
    """Stream a bz2 Wikipedia XML dump and insert articles into MongoDB.

    Uses insert_or_skip so document_metrics (e.g. word_counts) are computed on ingest.

    Args:
        dump_path: Path to the .xml.bz2 dump.
        mongodb_client: MongoDBCorpusClient (or compatible).
        source: Document source key (e.g. "wikipedia", "wikipedia_ea").
        language_code: Metadata language_code (e.g. "hyw", "hye").
        dump_file_name: Optional dump filename for metadata (defaults to dump_path.name).
        config: Pipeline config (for compute_metrics_on_ingest).

    Returns:
        Dict with inserted, duplicates, errors, skipped.
    """
    logger.info("Extracting articles from %s -> MongoDB (source=%s)", dump_path, source)
    stats = {"inserted": 0, "duplicates": 0, "errors": 0, "skipped": 0}
    name = dump_file_name or dump_path.name
    cfg = config or {}

    with bz2.open(dump_path, "rt", encoding="utf-8") as fh:
        context = ET.iterparse(fh, events=("end",))
        title = ""
        ns = ""

        for _event, elem in context:
            tag = elem.tag.split("}", 1)[-1]

            if tag == "title":
                title = elem.text or ""
            elif tag == "ns":
                ns = elem.text or ""
            elif tag == "text" and ns == "0":
                raw = elem.text or ""
                if not raw or is_redirect(raw):
                    elem.clear()
                    stats["skipped"] += 1
                    continue

                cleaned = clean_wikitext(raw)
                if len(cleaned) < 50:
                    elem.clear()
                    stats["skipped"] += 1
                    continue

                wiki_url = f"https://{language_code}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                scraped = ScrapedDocument(
                    source_family=source,
                    text=cleaned,
                    title=title,
                    source_url=wiki_url,
                    source_language_code=language_code,
                    source_type="encyclopedia",
                    extra={"dump_file": name},
                )
                ok = insert_or_skip(mongodb_client, doc=scraped, config=cfg)
                if ok:
                    stats["inserted"] += 1
                    if stats["inserted"] % 1000 == 0:
                        logger.info(
                            "  Inserted %d articles (duplicates: %d, errors: %d)...",
                            stats["inserted"],
                            stats["duplicates"],
                            stats["errors"],
                        )
                else:
                    stats["duplicates"] += 1

            if tag == "page":
                elem.clear()

    logger.info(
        "Extraction complete: %d inserted, %d duplicates, %d errors, %d skipped",
        stats["inserted"],
        stats["duplicates"],
        stats["errors"],
        stats["skipped"],
    )
    return stats


def run_wikipedia_wa(config: dict) -> None:
    """Download and extract Western Armenian Wikipedia (hyw) to MongoDB."""
    raw_dir = Path(config.get("paths", {}).get("raw_dir", "data/raw")) / "wikipedia"
    wiki_cfg = config.get("scraping", {}).get("wikipedia", {})
    lang = wiki_cfg.get("language", "hyw")
    date = resolve_dump_date(lang, wiki_cfg.get("dump_date", "latest"))
    dump_path = download_dump(lang, date, raw_dir)

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        stats = extract_wikipedia_to_mongodb(
            dump_path,
            client,
            source="wikipedia",
            language_code=lang,
            config=config,
        )
        logger.info(
            "Wikipedia WA: %d inserted, %d duplicates, %d errors",
            stats["inserted"],
            stats["duplicates"],
            stats["errors"],
        )

    if config.get("paths", {}).get("delete_after_ingest", False) and dump_path.exists():
        dump_path.unlink()
        logger.info("Deleted dump after ingest: %s", dump_path)


def run_wikipedia_ea(config: dict) -> None:
    """Download and extract Eastern Armenian Wikipedia (hy) to MongoDB."""
    paths = config.get("paths", {})
    raw_dir = Path(paths.get("raw_dir", "data/raw")) / "wikipedia_ea"

    logger.info("=== Downloading EA Wikipedia ===")
    date = resolve_dump_date("hy", "latest")
    dump_path = download_dump("hy", date, raw_dir)

    logger.info("=== Extracting EA Wikipedia to MongoDB ===")
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError(
                "MongoDB unavailable. wikipedia_ea requires MongoDB. "
                "Ensure pymongo is installed and MongoDB is running."
            )
        stats = extract_wikipedia_to_mongodb(
            dump_path,
            client,
            source="wikipedia_ea",
            language_code="hye",
            config=config,
        )
        logger.info(
            "EA Wikipedia MongoDB: %d inserted, %d duplicates, %d errors, %d skipped",
            stats["inserted"],
            stats["duplicates"],
            stats["errors"],
            stats["skipped"],
        )

    if paths.get("delete_after_ingest", False) and dump_path.exists():
        dump_path.unlink()
        logger.info("Deleted dump after ingest: %s", dump_path)


def run_wikipedia(config: dict) -> None:
    """Run Western and/or Eastern Armenian Wikipedia based on config.

    Config:
      scraping.wikipedia.enabled: if true, run Western Armenian (default True)
      scraping.wikipedia.language: "hyw" (default)
      scraping.wikipedia.dump_date: "latest" or YYYYMMDD
      scraping.wikipedia.ea_enabled: if true, also run Eastern Armenian
      scraping.eastern_armenian.enabled: if true, also run Eastern Armenian Wikipedia
    """
    cfg = config or {}
    scraping_cfg = cfg.get("scraping", {})
    wiki_cfg = scraping_cfg.get("wikipedia", {})
    ea_cfg = scraping_cfg.get("eastern_armenian", {})

    run_wa = wiki_cfg.get("enabled", True)
    run_ea = ea_cfg.get("enabled", False) or wiki_cfg.get("ea_enabled", False)

    if run_wa:
        run_wikipedia_wa(cfg)
    if run_ea:
        run_wikipedia_ea(cfg)


# -----------------------------------------------------------------------------
#  Wikisource (API-based)
# -----------------------------------------------------------------------------

_WIKISOURCE_API_BASE = "https://hy.wikisource.org/w/api.php"
_WIKISOURCE_RETRY_DELAY = 2
_WIKISOURCE_USER_AGENT = "ArmenianCorpusCore/1.0 (Education/Research)"
_WIKISOURCE_HEADERS = {
    "User-Agent": _WIKISOURCE_USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "hy,en;q=0.9",
}
_CATEGORY_PREFIX_MAP = {
    "Category:": "\u053f\u0561\u057f\u0565\u0563\u0578\u0580\u056b\u0561:",  # Կdelays:
}


def _wikisource_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(_WIKISOURCE_HEADERS)
    return sess


def _normalize_category_title(category: str) -> str:
    for src_prefix, dst_prefix in _CATEGORY_PREFIX_MAP.items():
        if category.startswith(src_prefix):
            return dst_prefix + category[len(src_prefix) :]
    return category


def _wikisource_api_get(session: requests.Session, params: dict, retries: int = 5) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    for attempt in range(retries):
        try:
            resp = session.get(_WIKISOURCE_API_BASE, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            delay = _WIKISOURCE_RETRY_DELAY * (2 ** attempt)
            logger.warning(
                "Wikisource API request failed (attempt %d/%d, status=%s): %s",
                attempt + 1,
                retries,
                status,
                exc,
            )
            if attempt < retries - 1:
                time.sleep(min(delay, 30))
    raise RuntimeError(f"MediaWiki API request failed after {retries} attempts")


def _iter_wikisource_category_pages(session: requests.Session, category: str) -> list[str]:
    titles: list[str] = []
    params: dict = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": "500",
        "cmtype": "page",
    }
    while True:
        data = _wikisource_api_get(session, params)
        for member in data.get("query", {}).get("categorymembers", []):
            titles.append(member["title"])
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
    return titles


def _fetch_wikisource_page_wikitext(session: requests.Session, title: str) -> str:
    data = _wikisource_api_get(
        session,
        {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
        },
    )
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


def run_wikisource(config: dict) -> None:
    """Scrape Armenian Wikisource (hy.wikisource.org) into MongoDB.

    Uses config["scraping"]["wikisource"]["categories"] for category list.
    """
    categories: list[str] = config["scraping"]["wikisource"]["categories"]
    session = _wikisource_session()

    with open_mongodb_client(config) as mongodb_client:
        if mongodb_client is None:
            raise RuntimeError(
                "MongoDB is required for the Wikisource scraper. "
                "Ensure pymongo is installed and MongoDB is reachable."
            )

        stats = {"inserted": 0, "duplicates": 0, "skipped": 0}

        for category in categories:
            normalized_category = _normalize_category_title(category)
            logger.info("Processing category: %s", normalized_category)
            titles = _iter_wikisource_category_pages(session, normalized_category)
            logger.info("  Found %d pages", len(titles))

            if not titles:
                logger.warning(
                    "  No pages found for category '%s'. Verify the title on hy.wikisource.org.",
                    normalized_category,
                )
                continue

            cat_slug = normalized_category.replace(
                "\u053f\u0561\u057f\u0565\u0563\u0578\u0580\u056b\u0561:", ""
            ).replace(" ", "_")

            for title in titles:
                existing = mongodb_client.documents.find_one(
                    {"source": "wikisource", "title": title}
                )
                if existing:
                    stats["skipped"] += 1
                    continue

                raw_wikitext = _fetch_wikisource_page_wikitext(session, title)
                if not raw_wikitext:
                    continue

                if is_redirect(raw_wikitext):
                    stats["skipped"] += 1
                    logger.debug("Skipping redirect: %s", title)
                    continue

                text = clean_wikitext(raw_wikitext)
                if not text.strip():
                    stats["skipped"] += 1
                    continue

                wa_score = compute_wa_score(text)
                source_language_code = "hyw" if wa_score >= WA_SCORE_THRESHOLD else "hye"

                url = f"https://hy.wikisource.org/wiki/{title.replace(' ', '_')}"

                scraped = ScrapedDocument(
                    source_family="wikisource",
                    text=text,
                    title=title,
                    source_url=url,
                    source_language_code=source_language_code,
                    source_type="literature",
                    wa_score=wa_score,
                    extra={"category": cat_slug},
                )
                ok = insert_or_skip(mongodb_client, doc=scraped, config=config)
                if ok:
                    stats["inserted"] += 1
                    logger.info(
                        "  Inserted: %s [%s, wa_score=%.1f]",
                        title,
                        source_language_code,
                        wa_score,
                    )
                else:
                    stats["duplicates"] += 1
                    logger.debug("Duplicate page: %s", title)

                time.sleep(0.1)

        logger.info(
            "MongoDB insertion complete: %d inserted, %d duplicates, %d skipped",
            stats["inserted"],
            stats["duplicates"],
            stats["skipped"],
        )
