"""Unified news scraper: diaspora newspapers, Eastern Armenian agencies, and RSS feeds.

Combines:
- Diaspora newspapers (Aztag, Horizon Weekly, Asbarez) — Selenium-based
- Eastern Armenian news agencies (Armenpress, A1+, Armtimes, Aravot) — RSS/HTML
- RSS news (Armenian + international keyword-filtered feeds)

RSS feeds typically do **not** contain the full article text: they provide title, link,
description/summary, and often pubDate. Full text is obtained by following the article URL.
The news pipeline can (1) populate a separate **news_article_catalog** in MongoDB from all
RSS entries (title, url, summary, source_name, published_at) and (2) use that catalog to
drive full-article scraping and to inform the newspaper splitter helper (split_issue_into_articles).

Entry point: run(config). Uses a single MongoDB client for all three sub-runners.
"""

from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Shared constants (used by newspaper and ea_news; rss_news may override delay via config)
_MIN_ARMENIAN_CHARS = 30
_REQUEST_DELAY = 2.0  # seconds between requests


def _armenian_char_count(text: str) -> int:
    """Count Armenian script characters (U+0530–U+058F). Shared by newspaper and ea_news."""
    return sum(1 for c in text if "\u0530" <= c <= "\u058F")


@dataclass
class ArticleRecord:
    """Standardized article record for crawlers → Mongo (catalog + documents)."""

    source_id: str
    url: str
    title: str
    text: str
    publication_date: Optional[str] = None
    category: Optional[str] = None
    language_code: str = "und"
    content_type: str = "article"
    writing_category: Optional[str] = None
    # Extra metadata merged into the MongoDB document (e.g. wa_score, dialect)
    metadata: dict = field(default_factory=dict)


def _upsert_article_from_record(
    record: ArticleRecord,
    client,
    config: dict | None = None,
) -> bool:
    """Upsert article into news_article_catalog and documents; return True if inserted."""
    from ingestion._shared.helpers import insert_or_skip

    if client is None:
        return False

    cfg = config or {}
    catalog = getattr(client, "news_article_catalog", None)
    language_code = (record.language_code or "und").strip() or "und"
    writing_category = record.writing_category or record.category or "news"

    if catalog is not None and record.url:
        add_to_set = {
            "sources": record.source_id,
            "source_language_codes": language_code,
        }
        try:
            catalog.update_one(
                {"url": record.url},
                {
                    "$setOnInsert": {
                        "url": record.url,
                        "title": record.title,
                        "summary": None,
                        "published_at": record.publication_date,
                        "category": record.category or writing_category,
                        "tags": [],
                        "language_code": language_code,
                        "source_language_codes": [language_code],
                        "content_type": record.content_type,
                        "writing_category": writing_category,
                        "document_id": None,
                    },
                    "$addToSet": add_to_set,
                },
                upsert=True,
            )
        except Exception:
            logger.debug("Catalog upsert failed for %s", record.url)

    meta = {
        "source_type": "news",
        "category": record.category or writing_category,
        "published_at": record.publication_date,
        "tags": [],
        "rss_sources": [record.source_id],
        "language_code": language_code,
        "source_language_codes": [language_code],
        "content_type": record.content_type,
        "writing_category": writing_category,
    }
    # Merge any extra metadata the crawler attached (e.g. wa_score, dialect)
    if record.metadata:
        meta.update(record.metadata)

    inserted = insert_or_skip(
        client,
        source=record.source_id,
        title=record.title,
        text=record.text,
        url=record.url,
        metadata=meta,
        config=cfg,
    )

    if not inserted:
        return False

    if catalog is not None and record.url:
        try:
            doc = client.documents.find_one({"metadata.url": record.url}, {"_id": 1})
            if doc:
                from bson import ObjectId  # type: ignore[reportMissingImports]

                doc_id = doc["_id"]
                catalog.update_one(
                    {"url": record.url},
                    {
                        "$set": {
                            "document_id": str(doc_id) if isinstance(doc_id, ObjectId) else doc_id
                        }
                    },
                )
        except Exception:
            logger.debug("Could not set document_id for %s", record.url)

    return True


# --- Diaspora newspapers (ex newspaper.py) ---

def _is_probable_article_url(url: str) -> bool:
    lowered = url.lower()
    banned_segments = [
        "/category/",
        "/tag/",
        "/author/",
        "/search/",
        "/page/",
        "/feed",
        "/wp-json/",
    ]
    if any(seg in lowered for seg in banned_segments):
        return False
    return lowered.count("/") >= 4


@dataclass
class NewspaperSource:
    """Configuration for a single newspaper source."""

    name: str
    base_url: str
    listing_url_template: str  # must contain {page}
    article_link_selectors: list[str]
    content_selectors: list[str]
    max_pages: int = 50
    articles_per_page: int = 20
    allowed_path_prefixes: list[str] = field(default_factory=list)


AZTAG = NewspaperSource(
    name="aztag",
    base_url="https://aztagdaily.com",
    listing_url_template="https://aztagdaily.com/archives/category/featured/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
        ".td-module-title a",
        ".item-details h3 a",
    ],
    content_selectors=[
        ".td-post-content p",
        ".entry-content p",
        ".post-content p",
        "article .content p",
        ".tdb-block-inner p",
    ],
    max_pages=100,
)

HORIZON = NewspaperSource(
    name="horizon",
    # Use the /am/ (Armenian) version of the site so listings are Armenian-first.
    # The /en/ version mixes English and Armenian articles on the same pages.
    base_url="https://horizonweekly.ca/am",
    listing_url_template="https://horizonweekly.ca/am/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
        ".td-module-title a",
        ".jeg_post_title a",
        ".post-item-title a",
    ],
    content_selectors=[
        ".single-article p",
        ".td-post-content p",
        ".entry-content p",
        ".post-content p",
        ".content-inner p",
        "article p",
    ],
    max_pages=100,
)

ASBAREZ = NewspaperSource(
    name="asbarez",
    # Prefer Armenian site when available (asbarez.am serves Armenian content).
    base_url="https://asbarez.am",
    listing_url_template="https://asbarez.am/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=40,
)

HAIRENIK = NewspaperSource(
    name="hairenik",
    base_url="https://hairenik.com",
    listing_url_template="https://hairenik.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
        ".td-module-title a",
    ],
    content_selectors=[
        ".entry-content p",
        ".td-post-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=200,
)

ARMENIAN_WEEKLY = NewspaperSource(
    name="armenian_weekly",
    base_url="https://armenianweekly.com",
    listing_url_template="https://armenianweekly.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=200,
)

KEGHART = NewspaperSource(
    name="keghart",
    base_url="https://keghart.com",
    listing_url_template="https://keghart.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        "article a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=100,
)

NOR_OR = NewspaperSource(
    name="nor_or",
    base_url="https://noror.com",
    listing_url_template="https://noror.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        "article a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=100,
)

MARMARA = NewspaperSource(
    name="marmara",
    base_url="https://marmaragazetesi.com",
    listing_url_template="https://marmaragazetesi.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        "article a",
        ".post-title a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=100,
)

JAMANAG = NewspaperSource(
    name="jamanag",
    base_url="https://jamanakatert.com",
    listing_url_template="https://jamanakatert.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
        ".td-module-title a",
    ],
    content_selectors=[
        ".entry-content p",
        ".td-post-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=200,
)

MASSIS_POST = NewspaperSource(
    name="massis_post",
    base_url="https://massispost.com",
    listing_url_template="https://massispost.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=200,
)

MIRROR_SPECTATOR = NewspaperSource(
    name="mirror_spectator",
    base_url="https://mirrorspectator.com",
    listing_url_template="https://mirrorspectator.com/page/{page}",
    article_link_selectors=[
        "h2 a",
        ".entry-title a",
        ".post-title a",
        "article a",
    ],
    content_selectors=[
        ".entry-content p",
        ".post-content p",
        "article p",
    ],
    max_pages=200,
)

_NEWSPAPER_ALL_SOURCES = {
    "aztag": AZTAG,
    "horizon": HORIZON,
    "asbarez": ASBAREZ,
    "hairenik": HAIRENIK,
    "armenian_weekly": ARMENIAN_WEEKLY,
    "keghart": KEGHART,
    "nor_or": NOR_OR,
    "marmara": MARMARA,
    "jamanag": JAMANAG,
    "massis_post": MASSIS_POST,
    "mirror_spectator": MIRROR_SPECTATOR,
}


def _extract_urls_from_html(
    html: str,
    source: NewspaperSource,
    seen: set[str],
) -> list[str]:
    """Extract candidate article links from raw HTML as a resilient fallback."""
    soup = BeautifulSoup(html, "html.parser")
    extracted: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not isinstance(href, str):
            continue
        href, _ = urldefrag(href)
        if not href.startswith(source.base_url):
            continue
        if not _is_probable_article_url(href):
            continue
        if source.allowed_path_prefixes:
            if not any(prefix in href for prefix in source.allowed_path_prefixes):
                continue
        if href in seen:
            continue
        seen.add(href)
        extracted.append(href)
    return extracted


def _init_driver():
    """Create a headless Chrome Selenium WebDriver with anti-detection."""
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.webdriver import WebDriver as Chrome

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def _load_already_scraped_urls(client, source_name: str) -> set[str]:
    """Load already-scraped URLs from MongoDB for resume."""
    seen: set[str] = set()
    if client is None:
        return seen
    cursor = client.documents.find(
        {"source": f"newspaper:{source_name}"},
        {"metadata.url": 1},
    )
    for doc in cursor:
        url = doc.get("metadata", {}).get("url")
        if url:
            seen.add(url)
    return seen


def _collect_article_urls(driver, source: NewspaperSource) -> list[str]:
    """Paginate through listing pages and collect unique article URLs."""
    from selenium.webdriver.common.by import By

    all_urls: list[str] = []
    seen: set[str] = set()

    max_pages = source.max_pages or 10_000
    for page_num in range(1, max_pages + 1):
        url = source.listing_url_template.format(page=page_num)
        logger.info("  Listing page %d: %s", page_num, url)
        try:
            driver.get(url)
            time.sleep(_REQUEST_DELAY)
        except Exception as exc:
            logger.warning("  Failed to load listing page %d: %s", page_num, exc)
            break

        found_on_page = 0
        for selector in source.article_link_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    href = el.get_attribute("href")
                    if not href:
                        continue
                    href, _ = urldefrag(href)
                    if not href.startswith(source.base_url):
                        continue
                    if not _is_probable_article_url(href):
                        continue
                    if source.allowed_path_prefixes:
                        if not any(prefix in href for prefix in source.allowed_path_prefixes):
                            continue
                    if href not in seen:
                        seen.add(href)
                        all_urls.append(href)
                        found_on_page += 1
            except Exception:
                continue

        if found_on_page == 0:
            try:
                fallback_urls = _extract_urls_from_html(driver.page_source, source, seen)
                if fallback_urls:
                    all_urls.extend(fallback_urls)
                    found_on_page += len(fallback_urls)
            except Exception:
                pass

        if found_on_page == 0:
            try:
                resp = requests.get(
                    url,
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.ok:
                    fallback_urls = _extract_urls_from_html(resp.text, source, seen)
                    if fallback_urls:
                        all_urls.extend(fallback_urls)
                        found_on_page += len(fallback_urls)
            except Exception:
                pass

        logger.info("  Found %d new article URLs on page %d", found_on_page, page_num)
        if found_on_page == 0:
            logger.info("  No articles found on page %d — stopping pagination", page_num)
            break

    logger.info("  Total unique article URLs collected: %d", len(all_urls))
    return all_urls


def _extract_article_text(driver, url: str, source: NewspaperSource) -> str:
    """Load an article URL and extract body text from <p> tags."""
    from selenium.webdriver.common.by import By

    logger.debug("Newspaper crawler: fetching article %s", url)
    driver.get(url)
    time.sleep(_REQUEST_DELAY)

    paragraphs: list[str] = []
    for selector in source.content_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                paragraphs = [el.text.strip() for el in elements if el.text.strip()]
                if paragraphs:
                    break
        except Exception:
            continue

    if not paragraphs:
        logger.warning("Newspaper crawler: no paragraphs extracted for %s (source=%s)", url, source.name)
    return "\n\n".join(paragraphs)


def _scrape_newspaper_source(
    source: NewspaperSource,
    client,
    max_articles: int = 0,
    min_armenian_chars: int = _MIN_ARMENIAN_CHARS,
    validate_wa: bool = False,
    config: dict | None = None,
) -> list[ArticleRecord]:
    """Scrape articles from a single newspaper source and return ArticleRecord list."""

    already_scraped = _load_already_scraped_urls(client, source.name)

    _compute_wa_score = None
    _wa_threshold = 5.0
    if validate_wa:
        try:
            from ingestion._shared.helpers import compute_wa_score as _cws, WA_SCORE_THRESHOLD as _thresh
            _compute_wa_score = _cws
            _wa_threshold = _thresh
        except ImportError:
            logger.warning("WA scorer unavailable for %s — language_code will default to 'hyw'", source.name)

    logger.info(
        "Scraping %s — %d articles already in MongoDB",
        source.name,
        len(already_scraped),
    )

    driver = _init_driver()
    new_records: list[ArticleRecord] = []
    try:
        urls = _collect_article_urls(driver, source)

        for url in urls:
            if url in already_scraped:
                continue
            if max_articles > 0 and len(new_records) >= max_articles:
                break

            try:
                text = _extract_article_text(driver, url, source)
            except Exception as exc:
                logger.warning("Newspaper crawler: failed to extract %s (%s): %s", url, source.name, exc)
                continue

            armenian_chars = _armenian_char_count(text)
            if armenian_chars < min_armenian_chars:
                logger.debug(
                    "Newspaper crawler: skipping (too few Armenian chars %d < %d): %s",
                    armenian_chars,
                    min_armenian_chars,
                    url,
                )
                continue

            # Classify dialect from actual text — do NOT trust the source's WA label.
            # EA content is kept and tagged, never silently discarded.
            detected_lc = "hyw"
            wa_score = 0.0
            if _compute_wa_score is not None:
                try:
                    wa_score = _compute_wa_score(text[:5000])
                    detected_lc = "hyw" if wa_score >= _wa_threshold else "hye"
                except Exception:
                    pass

            title = url.split("/")[-1] or url
            record = ArticleRecord(
                source_id=f"newspaper:{source.name}",
                url=url,
                title=title,
                text=text,
                publication_date=None,
                category="diaspora",
                language_code=detected_lc,
                content_type="article",
                writing_category="diaspora",
                metadata={
                    "wa_score": round(wa_score, 2),
                },
            )
            new_records.append(record)

            if len(new_records) % 50 == 0:
                logger.info("  Discovered %d candidate articles from %s…", len(new_records), source.name)

    finally:
        driver.quit()

    logger.info("Discovered %d candidate articles from %s", len(new_records), source.name)
    return new_records


def _run_newspapers(config: dict, client) -> None:
    """Run diaspora newspaper scraping (ex newspaper.run)."""
    news_cfg = config.get("scraping", {}).get("newspapers", {})
    sources_to_scrape: list[str] = news_cfg.get("sources", ["aztag", "horizon"])
    default_max_pages = int(news_cfg.get("max_pages", 100))
    default_max_articles = int(news_cfg.get("max_articles_per_source", 0))
    min_armenian_chars = int(news_cfg.get("min_armenian_chars", _MIN_ARMENIAN_CHARS))
    validate_wa = bool(news_cfg.get("validate_wa", True))
    source_overrides = news_cfg.get("source_overrides", {})

    for source_name in sources_to_scrape:
        source = _NEWSPAPER_ALL_SOURCES.get(source_name)
        if not source:
            logger.warning("Unknown newspaper source: %s", source_name)
            continue

        override_cfg = source_overrides.get(source_name, {}) if isinstance(source_overrides, dict) else {}
        runtime_source = NewspaperSource(
            name=source.name,
            base_url=source.base_url,
            listing_url_template=source.listing_url_template,
            article_link_selectors=list(source.article_link_selectors),
            content_selectors=list(source.content_selectors),
            max_pages=int(override_cfg.get("max_pages", default_max_pages)),
            articles_per_page=source.articles_per_page,
            allowed_path_prefixes=list(override_cfg.get("allowed_path_prefixes", source.allowed_path_prefixes)),
        )

        records = _scrape_newspaper_source(
            runtime_source,
            client=client,
            max_articles=int(override_cfg.get("max_articles", default_max_articles)),
            min_armenian_chars=min_armenian_chars,
            validate_wa=validate_wa,
            config=config,
        )
        inserted = 0
        for record in records:
            if _upsert_article_from_record(record, client, config=config):
                inserted += 1
        logger.info("[%s] MongoDB: %d/%d new articles inserted from %d discovered", source_name, inserted, len(records), len(records))


# --- Eastern Armenian news agencies (ex ea_news.py) ---

from ingestion._shared.metadata import TextMetadata, Region

_EA_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
}

NEWS_AGENCIES = {
    "armenpress": {
        "source_name": "Armenpress",
        "url": "https://armenpress.am/hy",
        "rss_urls": [],
        "fallback_seed_urls": [
            "https://armenpress.am/hy",
            "https://armenpress.am/hy/latest-news",
        ],
        "article_url_patterns": [
            r"^https?://(?:www\.)?armenpress\.am/hy/article/\d+/?$",
        ],
        "region": Region.ARMENIA,
    },
    "a1plus": {
        "source_name": "A1+",
        "url": "https://www.a1plus.am",
        "rss_urls": [
            "https://www.a1plus.am/hy/feed",
            "https://www.a1plus.am/feed",
        ],
        "region": Region.ARMENIA,
    },
    "armtimes": {
        "source_name": "Armtimes",
        "url": "https://armtimes.com",
        "rss_urls": [],
        "fallback_seed_urls": [
            "https://armtimes.com",
            "https://armtimes.com/hy/article/politics",
            "https://armtimes.com/hy/article/economy",
            "https://armtimes.com/hy/article/society",
            "https://armtimes.com/hy/article/world",
            "https://armtimes.com/hy/article/culture",
            "https://armtimes.com/hy/article/sport",
        ],
        "article_url_patterns": [
            r"^https?://(?:www\.)?armtimes\.com/hy/article/\d+/?$",
        ],
        "region": Region.ARMENIA,
    },
    "aravot": {
        "source_name": "Aravot",
        "url": "https://www.aravot.am",
        "rss_urls": [
            "https://www.aravot.am/feed/",
        ],
        "region": Region.ARMENIA,
    },
}


def _ea_parse_datetime(value: Optional[str]) -> Optional[str]:
    """Parse common RSS datetime formats and normalize to ISO string."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return None


def _ea_parse_rss_feed(feed_xml: str, base_url: str) -> list[dict[str, Optional[str]]]:
    """Parse RSS/Atom XML and return normalized item dictionaries."""
    items: list[dict[str, Optional[str]]] = []
    try:
        root = ET.fromstring(feed_xml)
    except ET.ParseError as exc:
        logger.warning("Invalid RSS/Atom XML: %s", exc)
        return items

    for node in root.findall(".//item"):
        raw_link = (node.findtext("link") or "").strip()
        if not raw_link:
            continue
        items.append({
            "title": (node.findtext("title") or "").strip() or None,
            "url": urljoin(base_url, raw_link),
            "published": _ea_parse_datetime(node.findtext("pubDate")),
            "category": (node.findtext("category") or "").strip() or None,
        })

    if items:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        link_node = entry.find("atom:link", ns)
        href = link_node.attrib.get("href") if link_node is not None else ""
        href = (href or "").strip()
        if not href:
            continue
        items.append({
            "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip() or None,
            "url": urljoin(base_url, href),
            "published": _ea_parse_datetime(
                entry.findtext("atom:updated", default="", namespaces=ns)
                or entry.findtext("atom:published", default="", namespaces=ns)
            ),
            "category": None,
        })

    return items


def _ea_extract_readable_text(html: str) -> str:
    """Extract readable article text from HTML document."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    containers = [
        soup.find("article"),
        soup.find("main"),
        soup.select_one(".article-content"),
        soup.select_one(".entry-content"),
        soup.select_one(".post-content"),
        soup.select_one(".content"),
        soup.body,
    ]

    best = ""
    for container in containers:
        if container is None:
            continue
        paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) >= 30]
        if paragraphs:
            candidate = "\n".join(paragraphs)
        else:
            candidate = container.get_text("\n", strip=True)
        candidate = re.sub(r"\n{3,}", "\n\n", candidate).strip()
        if len(candidate) > len(best):
            best = candidate

    return best


def _ea_fetch_feed_items(feed_url: str, timeout: int = 30) -> list[dict[str, Optional[str]]]:
    """Fetch and parse one RSS/Atom feed."""
    try:
        response = requests.get(feed_url, timeout=timeout, headers=_EA_DEFAULT_HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed feed request %s: %s", feed_url, exc)
        return []

    content_type = (response.headers.get("content-type") or "").lower()
    text = response.text or ""
    sample = text.lstrip()[:200].lower()
    looks_like_xml = any(token in content_type for token in ["xml", "rss", "atom"]) or sample.startswith("<?xml")
    if not looks_like_xml:
        return []

    return _ea_parse_rss_feed(text, base_url=feed_url)


def _ea_discover_feed_urls(base_url: str, timeout: int = 30) -> list[str]:
    """Discover RSS/Atom feed URLs from a site's homepage."""
    try:
        response = requests.get(base_url, timeout=timeout, headers=_EA_DEFAULT_HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed homepage request for feed discovery %s: %s", base_url, exc)
        return []

    soup = BeautifulSoup(response.text, "lxml")
    discovered: list[str] = []
    seen: set[str] = set()

    for link in soup.find_all("link"):
        rel_val = link.get("rel")
        rel_parts = rel_val if isinstance(rel_val, list) else [rel_val] if rel_val else []
        rel = " ".join(str(p) for p in rel_parts)
        href = str(link.get("href") or "").strip()
        typ = str(link.get("type") or "").lower()
        if not href:
            continue
        if "alternate" not in rel.lower() and "rss" not in href.lower() and "atom" not in href.lower():
            continue
        if "rss" not in typ and "atom" not in typ and "xml" not in typ and "rss" not in href.lower() and "atom" not in href.lower():
            continue
        absolute = urljoin(base_url, href)
        if absolute not in seen:
            seen.add(absolute)
            discovered.append(absolute)

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        lower_href = href.lower()
        if "rss" in lower_href or "feed" in lower_href or "atom" in lower_href:
            absolute = urljoin(base_url, href)
            if absolute not in seen:
                seen.add(absolute)
                discovered.append(absolute)

    return discovered


def _ea_extract_candidate_article_urls(
    html: str,
    base_url: str,
    article_url_patterns: list[str],
) -> list[str]:
    """Extract candidate article URLs from a listing/homepage document."""
    soup = BeautifulSoup(html, "lxml")
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in article_url_patterns]

    candidates: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href).split("#", 1)[0]
        if "?" in absolute:
            absolute = absolute.split("?", 1)[0]
        if absolute in seen:
            continue
        if not absolute.lower().startswith("http"):
            continue
        if regexes and not any(regex.match(absolute) for regex in regexes):
            continue
        seen.add(absolute)
        candidates.append(absolute)

    return candidates


def _ea_collect_fallback_article_urls(
    agency_name: str,
    agency_config: dict,
    target_count: int,
    timeout: int = 30,
) -> list[str]:
    """Collect article URLs by crawling listing pages when feeds are unavailable."""
    seeds = agency_config.get("fallback_seed_urls") or [agency_config["url"]]
    patterns = agency_config.get("article_url_patterns") or []

    found: list[str] = []
    seen: set[str] = set()

    for seed in seeds:
        if len(found) >= target_count:
            break
        try:
            response = requests.get(seed, timeout=timeout, headers=_EA_DEFAULT_HEADERS)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("EA crawler: %s fallback seed request failed %s: %s", agency_name, seed, exc)
            continue

        urls = _ea_extract_candidate_article_urls(response.text, seed, patterns)
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            found.append(url)
            if len(found) >= target_count:
                break

    return found


def _ea_extract_article_page_metadata(html: str) -> dict[str, Optional[str]]:
    """Extract title/date/category hints from an article page HTML."""
    soup = BeautifulSoup(html, "lxml")

    title = None
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag) and og_title.get("content"):
        raw = og_title.get("content", "")
        title = (raw[0] if isinstance(raw, list) else raw or "").strip() or None
    if not title and soup.title and soup.title.text:
        title = soup.title.text.strip() or None
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True) or None

    published_raw = None
    for selector in [
        ("meta", {"property": "article:published_time"}, "content"),
        ("meta", {"name": "pubdate"}, "content"),
        ("meta", {"name": "publish-date"}, "content"),
        ("time", {"datetime": True}, "datetime"),
    ]:
        tag_name, attrs, key = selector
        node = soup.find(tag_name, attrs=attrs)
        if isinstance(node, Tag) and node.get(key):
            published_raw = node.get(key)
            break
    if isinstance(published_raw, list):
        published_raw = published_raw[0] if published_raw else None

    category = None
    section_node = soup.find("meta", property="article:section")
    if isinstance(section_node, Tag) and section_node.get("content"):
        raw = section_node.get("content", "")
        category = (raw[0] if isinstance(raw, list) else raw or "").strip() or None

    return {
        "title": title,
        "published": _ea_parse_datetime(published_raw),
        "category": category,
    }


def _ea_fetch_article_payload(url: str, timeout: int = 30) -> Optional[dict[str, Optional[str]]]:
    """Fetch article URL and return extracted text + metadata payload."""
    try:
        logger.debug("EA crawler: fetching article %s", url)
        response = requests.get(url, timeout=timeout, headers=_EA_DEFAULT_HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("EA crawler: article request failed %s: %s", url, exc)
        return None

    html = response.text
    text = _ea_extract_readable_text(html)
    if len(text) < 250:
        logger.warning("EA crawler: too-short article (<250 chars) for %s", url)
        return None
    if _armenian_char_count(text) < _MIN_ARMENIAN_CHARS:
        logger.warning("EA crawler: too few Armenian chars for %s", url)
        return None

    meta = _ea_extract_article_page_metadata(html)
    return {
        "text": text,
        "title": meta.get("title"),
        "published": meta.get("published"),
        "category": meta.get("category"),
    }


def _scrape_ea_news_agency(
    agency_name: str,
    max_articles: int = 500,
    config: dict | None = None,
) -> list[ArticleRecord]:
    """Scrape a single Eastern Armenian news agency and return ArticleRecord list."""

    if agency_name not in NEWS_AGENCIES:
        raise ValueError(f"Unknown news agency: {agency_name}")

    agency_config = NEWS_AGENCIES[agency_name]
    base_url = agency_config["url"]
    source_name = agency_config["source_name"]
    feed_urls = agency_config.get("rss_urls", [])
    source_id = f"eastern_armenian_news:{agency_name}"
    extraction_date = datetime.now().isoformat()

    logger.info("Scraping %s news agency from %s...", agency_name, base_url)

    scraped = 0
    records: list[ArticleRecord] = []
    seen_urls: set[str] = set()

    all_feed_urls = list(feed_urls)
    discovered_feeds = _ea_discover_feed_urls(base_url)
    for discovered in discovered_feeds:
        if discovered not in all_feed_urls:
            all_feed_urls.append(discovered)

    for feed_url in all_feed_urls:
        items = _ea_fetch_feed_items(feed_url)
        if not items:
            continue

        for item in items:
            if max_articles > 0 and len(records) >= max_articles:
                break

            article_url = item.get("url")
            if not article_url or article_url in seen_urls:
                continue

            seen_urls.add(article_url)
            scraped += 1

            payload = _ea_fetch_article_payload(article_url)
            if not payload:
                continue

            article_text = payload["text"]
            raw_title = item.get("title") or payload.get("title") or f"{agency_name}_{scraped}"

            meta = TextMetadata.eastern_news_agency(
                source_name=source_name,
                publication_date=item.get("published") or payload.get("published"),
                extraction_date=extraction_date,
            )
            meta.source_url = article_url
            meta.category = item.get("category") or payload.get("category")
            meta.extra = {
                "agency_key": agency_name,
                "article_title": raw_title,
                "feed_url": feed_url,
            }

            record = ArticleRecord(
                source_id=source_id,
                url=article_url,
                title=raw_title,
                text=article_text or "",
                publication_date=meta.publication_date,
                category=meta.category or "news",
                language_code="hye",
                content_type="article",
                writing_category="news",
            )
            records.append(record)

            if len(records) % 50 == 0:
                logger.info("%s: discovered %d/%d articles", agency_name, len(records), max_articles)

            time.sleep(_REQUEST_DELAY)

        if max_articles > 0 and len(records) >= max_articles:
            break

    if max_articles > 0 and len(records) < max_articles:
        remaining = max_articles - len(records)
        fallback_urls = _ea_collect_fallback_article_urls(agency_name, agency_config, target_count=remaining * 3)
        if fallback_urls:
            logger.info("%s: fallback discovered %d article URLs", agency_name, len(fallback_urls))

        for article_url in fallback_urls:
            if len(records) >= max_articles:
                break
            if article_url in seen_urls:
                continue

            seen_urls.add(article_url)
            scraped += 1

            payload = _ea_fetch_article_payload(article_url)
            if not payload:
                continue

            raw_title = payload.get("title") or f"{agency_name}_{scraped}"
            article_text = payload["text"]

            meta = TextMetadata.eastern_news_agency(
                source_name=source_name,
                publication_date=payload.get("published"),
                extraction_date=extraction_date,
            )
            meta.source_url = article_url
            meta.category = payload.get("category")
            meta.extra = {
                "agency_key": agency_name,
                "article_title": raw_title,
                "feed_url": None,
                "ingest_method": "fallback_listing_crawl",
            }

            record = ArticleRecord(
                source_id=source_id,
                url=article_url,
                title=raw_title,
                text=article_text or "",
                publication_date=meta.publication_date,
                category=meta.category or "news",
                language_code="hye",
                content_type="article",
                writing_category="news",
            )
            records.append(record)

            if len(records) % 50 == 0:
                logger.info("%s: discovered %d/%d articles", agency_name, len(records), max_articles)

            time.sleep(_REQUEST_DELAY)

    return records


def _run_eastern_armenian(config: dict, client) -> None:
    """Run Eastern Armenian news agency scraping (ex ea_news.run)."""
    ea_cfg = config.get("scraping", {}).get("eastern_armenian", {})
    max_articles = int(ea_cfg.get("max_articles_per_agency", 0))

    logger.info("=== Scraping EA News Agencies ===")
    results = {}
    for agency_name in NEWS_AGENCIES:
        try:
            records = _scrape_ea_news_agency(
                agency_name,
                max_articles=max_articles,
                config=config,
            )
            inserted = 0
            for record in records:
                if _upsert_article_from_record(record, client, config=config):
                    inserted += 1
            results[agency_name] = (len(records), inserted)
            time.sleep(_REQUEST_DELAY)
        except Exception as exc:
            logger.error("Error scraping %s: %s", agency_name, exc)
            results[agency_name] = (0, 0)
    for agency, (scraped, inserted) in results.items():
        logger.info("%s: scraped=%d, inserted=%d", agency, scraped, inserted)


# --- RSS news (ex rss_news.py) ---

_RSS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Diaspora newspapers (same as Selenium newspaper sources): include in RSS process so catalog gets their articles too. Mark hyw (Western Armenian).
_DIASPORA_NEWSPAPER_RSS_SOURCES: list[dict] = [
    {"name": "Aztag", "url": "https://aztagdaily.com", "rss": "https://aztagdaily.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Horizon Weekly", "url": "https://horizonweekly.ca", "rss": "https://horizonweekly.ca/am/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Asbarez", "url": "https://asbarez.com", "rss": "https://asbarez.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Hairenik", "url": "https://hairenik.com", "rss": "https://hairenik.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Keghart", "url": "https://keghart.com", "rss": "https://keghart.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Nor Or", "url": "https://noror.com", "rss": "https://noror.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Marmara", "url": "https://marmaragazetesi.com", "rss": "https://marmaragazetesi.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Jamanag", "url": "https://jamanakatert.com", "rss": "https://jamanakatert.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Massis Post", "url": "https://massispost.com", "rss": "https://massispost.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Armenian Mirror-Spectator", "url": "https://mirrorspectator.com", "rss": "https://mirrorspectator.com/feed/", "category": "diaspora", "language_code": "hyw"},
]

# Republic of Armenia sources: prefer Armenian feeds when the site offers them; mark Armenian content as hye (Eastern).
# language_code: ISO 639-3 (hyw=Western, hye=Eastern, eng=English, hy=undetermined).
_ARMENIAN_SOURCES: list[dict] = [
    {"name": "Armenpress", "url": "https://armenpress.am/hy/news/", "rss": "https://armenpress.am/hy/rss/news/", "category": "news", "language_code": "hye"},
    {"name": "Armenian Weekly", "url": "https://armenianweekly.com", "rss": "https://armenianweekly.com/feed/", "category": "news", "language_code": "hyw"},
    {"name": "Azatutyun", "url": "https://www.azatutyun.am", "rss": "https://www.azatutyun.am/api/zijrreypui", "category": "news", "language_code": "hye"},
    {"name": "Hetq", "url": "https://hetq.am/hy/news", "rss": "https://hetq.am/hy/rss", "category": "investigative", "language_code": "hye"},
    {"name": "Panorama.am", "url": "https://www.panorama.am", "rss": "https://www.panorama.am/rss/?lang=hy", "category": "news", "language_code": "hye"},
    {"name": "EVN Report", "url": "https://evnreport.com", "rss": "https://evnreport.com/feed/", "category": "analysis", "language_code": "eng"},
    {"name": "OC Media", "url": "https://oc-media.org", "rss": "https://oc-media.org/feed/", "category": "news", "language_code": "eng"},
    {"name": "Civilnet", "url": "https://www.civilnet.am", "rss": "https://www.civilnet.am/feed/", "category": "culture", "language_code": "hye"},
    {"name": "Massis Post", "url": "https://massispost.com", "rss": "https://massispost.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Armenian Mirror-Spectator", "url": "https://mirrorspectator.com", "rss": "https://mirrorspectator.com/feed/", "category": "diaspora", "language_code": "hyw"},
    {"name": "Agos", "url": "https://www.agos.com.tr/am", "rss": "https://www.agos.com.tr/am/rss", "category": "diaspora", "language_code": "hyw"},
]

_INTERNATIONAL_SOURCES: list[dict] = [
    {"name": "Google News - Armenia", "url": "https://news.google.com",
     "rss": "https://news.google.com/rss/search?q=Armenia+OR+Armenian+OR+Artsakh+OR+Karabakh&hl=en-US&gl=US&ceid=US:en",
     "category": "international", "keyword_filter": False, "google_news": True, "language_code": "eng"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com", "rss": "https://www.aljazeera.com/xml/rss/all.xml", "category": "international", "keyword_filter": True, "language_code": "eng"},
    {"name": "Al-Monitor", "url": "https://www.al-monitor.com", "rss": "https://www.al-monitor.com/rss", "category": "international", "keyword_filter": True, "language_code": "eng"},
    {"name": "BBC World", "url": "https://www.bbc.co.uk/news/world", "rss": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "international", "keyword_filter": True, "language_code": "eng"},
    {"name": "France 24", "url": "https://www.france24.com/en/", "rss": "https://www.france24.com/en/rss", "category": "international", "keyword_filter": True, "language_code": "eng"},
    {"name": "Deutsche Welle", "url": "https://www.dw.com/en/", "rss": "https://rss.dw.com/xml/rss-en-world", "category": "international", "keyword_filter": True, "language_code": "eng"},
    {"name": "Euronews", "url": "https://www.euronews.com", "rss": "https://www.euronews.com/rss", "category": "international", "keyword_filter": True, "language_code": "eng"},
]

ALL_RSS_SOURCES = _DIASPORA_NEWSPAPER_RSS_SOURCES + _ARMENIAN_SOURCES + _INTERNATIONAL_SOURCES

ARMENIAN_KEYWORDS: list[str] = [
    r"\barmenia\b", r"\barmenian[s]?\b", r"\bhay(?:astan)?\b",
    r"\byerevan\b", r"\bgyumri\b", r"\bvanadzor\b", r"\bsevan\b",
    r"\bararat\b", r"\bechmiadzin\b", r"\betchmiadzin\b",
    r"\bartsakh\b", r"\bkarabakh\b", r"\bnagorno[- ]?karabakh\b",
    r"\bstepanakert\b", r"\bshushi\b", r"\bshusha\b",
    r"\barmenian[- ]?genocide\b", r"\bmedz\s*yeghern\b", r"\baghet\b",
    r"\bapril\s*24\b",
    r"\bpash[iy]n[iy]an\b", r"\bkoch?ar[iy]an\b", r"\bsark?[iy]ss?[iy]an\b",
    r"\bazerbaijan\b.*(?:armenia|ceasefire|border|peace|corridor)",
    r"\bturkey\b.*(?:armenia|border|protocol|normali[sz])",
    r"\bzangezur\s*corridor\b", r"\bminsk\s*group\b",
    r"\b44[- ]?day\s*war\b",
    r"\barmenian[- ]?diaspora\b", r"\barmenian[- ]?apostolic\b",
    r"\bduduk\b", r"\blavash\b", r"\bkhachkar\b",
    r"\baznavour\b", r"\btankian\b", r"\bsystem\s+of\s+a\s+down\b",
    r"\bkomitas\b", r"\bparajanov\b",
    r"\bsouth[- ]?caucasus\b", r"\bcaucasus\b.*armenian",
]

_RSS_KEYWORD_PATTERN: re.Pattern[str] = re.compile(
    "|".join(ARMENIAN_KEYWORDS), re.IGNORECASE,
)


def _rss_matches_armenian_keywords(text: str) -> bool:
    return bool(_RSS_KEYWORD_PATTERN.search(text))


RSS_BLOCKED_SOURCES: set[str] = {
    "rt", "russia today", "rt.com", "sputnik", "sputniknews",
    "tass", "ria novosti", "ria news",
    "azernews", "azertag", "apa.az", "report.az", "caliber.az",
    "trend.az", "news.az", "day.az",
    "trt", "trt world", "anadolu agency", "daily sabah",
}

RSS_DUPLICATE_SOURCES: set[str] = {
    "armenpress", "asbarez", "the armenian weekly", "armenian weekly",
    "azatutyun", "radio free europe", "rfe/rl",
    "hetq", "hetq.am", "panorama.am",
    "evn report", "oc media", "civilnet",
    "massis post", "the armenian mirror-spectator",
    "mirror-spectator", "mirrorspectator",
    "horizon weekly", "agos",
    "hairenik", "hairenik weekly",
    "keghart", "keghart.com",
    "nor or", "noror",
    "marmara", "marmara gazetesi",
    "euronews", "france 24", "al jazeera", "al-monitor",
    "bbc", "bbc world", "bbc news",
    "deutsche welle", "dw",
}

_RSS_BLOCKED_RE = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in RSS_BLOCKED_SOURCES) + r")\s*$",
    re.IGNORECASE,
)

_RSS_DUPLICATE_RE = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in RSS_DUPLICATE_SOURCES) + r")\s*$",
    re.IGNORECASE,
)


def _rss_google_news_source_blocked(title: str) -> bool:
    parts = title.rsplit(" - ", 1)
    if len(parts) < 2:
        return False
    return bool(_RSS_BLOCKED_RE.search(parts[-1].strip()))


def _rss_google_news_source_duplicate(title: str) -> bool:
    parts = title.rsplit(" - ", 1)
    if len(parts) < 2:
        return False
    return bool(_RSS_DUPLICATE_RE.search(parts[-1].strip()))


def _rss_parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def _rss_clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _rss_strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator=" ")


_RSS_ARTICLE_SELECTORS = [
    "article",
    ".single-article",
    '[itemprop="articleBody"]',
    ".article-body",
    ".entry-content",
    ".post-content",
    ".story-body",
    ".field-name-body",
    "#article-body",
    ".article__body",
    ".text-long",
    "main .content",
]


def fetch_full_article(url: str, session: requests.Session, timeout: int = 15) -> str | None:
    """Follow an article URL and extract the full body text."""
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    try:
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None

    for tag in soup.select("script, style, nav, header, footer, aside, .sidebar, .ad, .advertisement"):
        tag.decompose()

    for selector in _RSS_ARTICLE_SELECTORS:
        container = soup.select_one(selector)
        if container:
            paragraphs = container.find_all("p")
            text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if len(text) >= 100:
                return _rss_clean_text(text)

    paragraphs = soup.find_all("p")
    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    if len(text) >= 200:
        return _rss_clean_text(text)

    return None


def _rss_fetch_feed(rss_url: str, session: requests.Session) -> list[dict]:
    """Parse an RSS/Atom feed and return a list of entry dicts."""
    try:
        import feedparser  # type: ignore[reportMissingImports]
        feed = feedparser.parse(rss_url)
        entries = []
        for e in feed.entries:
            title = str(e.get("title", "")).strip()
            url = str(e.get("link", "")).strip()
            if not title or not url:
                continue
            raw_summary = str(e.get("summary", e.get("description", "")))
            summary = _rss_clean_text(_rss_strip_html(raw_summary))[:1000]
            published = _rss_parse_date(
                str(e.get("published", e.get("updated", "")) or "")
            )
            raw_tags = e.get("tags") or []
            tags = [str(t.get("term", "")) for t in raw_tags if t and t.get("term")]
            entries.append({
                "title": title,
                "url": url,
                "summary": summary,
                "published_at": published.isoformat() if published else None,
                "tags": tags,
            })
        return entries
    except ImportError:
        logger.warning("feedparser not installed; using basic XML parsing")
        return _rss_fetch_feed_xml(rss_url, session)


def _rss_fetch_feed_xml(rss_url: str, session: requests.Session) -> list[dict]:
    """Minimal RSS/Atom parser using stdlib xml.etree."""
    try:
        resp = session.get(rss_url, timeout=20)
        resp.raise_for_status()
        time.sleep(_REQUEST_DELAY)
    except requests.RequestException as exc:
        logger.error("Failed to fetch feed %s: %s", rss_url, exc)
        return []

    entries = []
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        logger.error("XML parse error for %s: %s", rss_url, exc)
        return []

    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        desc = _rss_clean_text(_rss_strip_html(item.findtext("description") or ""))[:1000]
        pub = _rss_parse_date(item.findtext("pubDate") or "")
        entries.append({
            "title": title,
            "url": url,
            "summary": desc,
            "published_at": pub.isoformat() if pub else None,
            "tags": [],
        })

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry_el in root.findall(".//atom:entry", ns):
        title = (entry_el.findtext("atom:title", namespaces=ns) or "").strip()
        link_el = entry_el.find("atom:link[@rel='alternate']", ns)
        if link_el is None:
            link_el = entry_el.find("atom:link", ns)
        url = (link_el.get("href", "") if link_el is not None else "").strip()
        if not title or not url:
            continue
        summary_el = entry_el.findtext("atom:summary", namespaces=ns) or ""
        pub_str = entry_el.findtext("atom:updated", namespaces=ns) or ""
        pub = _rss_parse_date(pub_str)
        entries.append({
            "title": title,
            "url": url,
            "summary": _rss_clean_text(_rss_strip_html(summary_el))[:1000],
            "published_at": pub.isoformat() if pub else None,
            "tags": [],
        })

    return entries


def _rss_scrape_source(source: dict, session: requests.Session) -> list[dict]:
    """Scrape a single RSS source, applying filtering as configured."""
    name = source["name"]
    rss_url = source["rss"]
    logger.info("[%s] Fetching RSS feed: %s", name, rss_url)

    entries = _rss_fetch_feed(rss_url, session)

    if source.get("keyword_filter"):
        before = len(entries)
        entries = [
            e for e in entries
            if _rss_matches_armenian_keywords(e["title"])
            or _rss_matches_armenian_keywords(e.get("summary", ""))
        ]
        logger.info(
            "[%s] Keyword filter: %d/%d matched Armenian keywords",
            name, len(entries), before,
        )

    if source.get("google_news"):
        before = len(entries)
        entries = [
            e for e in entries
            if not _rss_google_news_source_blocked(e["title"])
            and not _rss_google_news_source_duplicate(e["title"])
        ]
        logger.info(
            "[%s] Source filter: kept %d/%d (blocked/duplicate removed)",
            name, len(entries), before,
        )

    for e in entries:
        e["source_name"] = name
        e["source_url"] = source["url"]
        e["category"] = source.get("category", "news")

    logger.info("[%s] Collected %d articles", name, len(entries))
    return entries


def _load_existing_urls(jsonl_path: Path) -> set[str]:
    urls: set[str] = set()
    if not jsonl_path.exists():
        return urls
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                data = json.loads(line)
                urls.add(data.get("url", ""))
            except (json.JSONDecodeError, ValueError):
                continue
    return urls


def _append_articles(jsonl_path: Path, articles: list[dict]) -> int:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(jsonl_path, "a", encoding="utf-8") as fh:
        for a in articles:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
            count += 1
    return count


def _populate_news_article_catalog(config: dict, client) -> int:
    """Populate news_article_catalog from all RSS feeds. One catalog document per article URL.

    When the same article appears in multiple feeds, we keep a single catalog entry and record
    all sources in the `sources` and `feed_urls` arrays. Does not overwrite `document_id` if
    already set (link to the representative document in the documents collection).
    """
    rss_cfg = config.get("scraping", {}).get("rss_news", {})
    if not rss_cfg.get("populate_catalog", True):
        return 0
    enabled_sources = rss_cfg.get("sources")
    request_delay = rss_cfg.get("request_delay", _REQUEST_DELAY)
    session = requests.Session()
    session.headers.update(_RSS_HEADERS)
    catalog = getattr(client, "news_article_catalog", None)
    if catalog is None:
        logger.warning("news_article_catalog not available; skip populate")
        return 0
    total = 0
    for source in ALL_RSS_SOURCES:
        if enabled_sources and source["name"] not in enabled_sources:
            continue
        try:
            entries = _rss_scrape_source(source, session)
        except Exception:
            logger.exception("[%s] Feed fetch failed", source["name"])
            continue
        feed_url = source.get("rss")
        for entry in entries:
            url = entry.get("url")
            if not url:
                continue
            title = entry.get("title", "") or ""
            summary = entry.get("summary", "") or ""
            published_at = entry.get("published_at")
            category = entry.get("category", "news")
            tags = entry.get("tags", []) or []
            # Tagging: language_code from source (ISO 639-3/BCP 47); source_language_codes recorded on insert
            language_code = source.get("language_code") or "und"
            content_type = "article"
            writing_category = category  # news, analysis, diaspora, international, etc.
            try:
                # Do not $addToSet on source_language_codes to avoid type conflicts; it is set only on insert.
                add_to_set = {"sources": source["name"]}
                if feed_url:
                    add_to_set["feed_urls"] = feed_url
                result = catalog.update_one(
                    {"url": url},
                    {
                        "$setOnInsert": {
                            "url": url,
                            "title": title,
                            "summary": summary,
                            "published_at": published_at,
                            "category": category,
                            "tags": tags,
                            "language_code": language_code,
                            "source_language_codes": [language_code],
                            "content_type": content_type,
                            "writing_category": writing_category,
                            "document_id": None,
                        },
                        "$addToSet": add_to_set,
                    },
                    upsert=True,
                )
                if result.upserted_id:
                    total += 1
            except Exception:
                logger.exception("Catalog update failed for %s", url)
        time.sleep(request_delay)
    logger.info("news_article_catalog: %d new/updated URLs from RSS", total)
    return total


def _run_scrape_from_news_catalog(config: dict, client) -> None:
    """Scrape full article for each catalog entry that has no document_id yet; insert into documents and set catalog.document_id.

    Runs standard enrichment (insert_or_skip → metrics, drift, etc.). One document per article URL;
    catalog entries hold a meta link (document_id) to their representative document.
    """
    from ingestion._shared.helpers import insert_or_skip

    catalog = getattr(client, "news_article_catalog", None)
    if catalog is None:
        logger.warning("news_article_catalog not available; skip scrape-from-catalog")
        return
    rss_cfg = config.get("scraping", {}).get("rss_news", {})
    request_delay = rss_cfg.get("request_delay", _REQUEST_DELAY)
    session = requests.Session()
    session.headers.update(_RSS_HEADERS)
    inserted = 0
    for cat_doc in catalog.find({"$or": [{"document_id": None}, {"document_id": {"$exists": False}}]}):
        url = cat_doc.get("url")
        if not url:
            continue
        # If document already exists (e.g. from a previous run), link it and skip fetch
        existing_doc = client.documents.find_one({"metadata.url": url}, {"_id": 1})
        if existing_doc:
            try:
                from bson import ObjectId  # type: ignore[reportMissingImports]
                doc_id = existing_doc["_id"]
                catalog.update_one(
                    {"url": url},
                    {"$set": {"document_id": str(doc_id) if isinstance(doc_id, ObjectId) else doc_id}},
                )
            except Exception:
                logger.debug("Could not set document_id for %s", url)
            continue
        full_text = fetch_full_article(url, session)
        text = full_text or cat_doc.get("summary", "") or cat_doc.get("title", "")
        if not text:
            continue
        sources = cat_doc.get("sources") or []
        source_tag = f"rss_news:{sources[0]}" if sources else "rss_news:unknown"
        # Detailed tagging for filtering and downstream pipelines (language_code, source_language_codes, content_type, writing_category)
        meta = {
            "source_type": "news",
            "category": cat_doc.get("category", "news"),
            "published_at": cat_doc.get("published_at"),
            "tags": cat_doc.get("tags", []),
            "rss_sources": sources,
            "language_code": cat_doc.get("language_code") or "und",
            "source_language_codes": cat_doc.get("source_language_codes") or cat_doc.get("language_codes") or [],
            "content_type": cat_doc.get("content_type") or "article",
            "writing_category": cat_doc.get("writing_category") or "news",
        }
        if insert_or_skip(
            client,
            source=source_tag,
            title=cat_doc.get("title", ""),
            text=text,
            url=url,
            metadata=meta,
            config=config,
        ):
            inserted += 1
        # Link catalog to document (whether we just inserted or it was a duplicate)
        try:
            doc = client.documents.find_one({"metadata.url": url}, {"_id": 1})
            if doc:
                from bson import ObjectId  # type: ignore[reportMissingImports]
                doc_id = doc["_id"]
                catalog.update_one(
                    {"url": url},
                    {"$set": {"document_id": str(doc_id) if isinstance(doc_id, ObjectId) else doc_id}},
                )
        except Exception:
            logger.debug("Could not set document_id for %s", url)
        time.sleep(request_delay)
    logger.info("Scrape-from-catalog: %d new documents inserted; catalog document_id links updated", inserted)


def _run_rss_news(config: dict, client) -> None:
    """Run RSS news as one process: (1) update catalog from all feeds, (2) scrape each new article and link catalog to documents.

    When populate_catalog is True (default): phase 1 upserts one catalog doc per URL with sources/feed_urls;
    phase 2 fetches full text for any catalog entry without document_id, inserts into documents (with
    standard enrichment), and sets catalog.document_id to the representative document. No duplicate
    full articles; catalog can list multiple sources for the same URL.
    When populate_catalog is False: legacy feed-based scrape only (no catalog).
    """
    rss_cfg = config.get("scraping", {}).get("rss_news", {})
    populate = rss_cfg.get("populate_catalog", True)

    if populate:
        _populate_news_article_catalog(config, client)
        _run_scrape_from_news_catalog(config, client)
        return

    # Legacy: fetch each feed and scrape full article per entry (no catalog)
    from ingestion._shared.helpers import insert_or_skip

    request_delay = rss_cfg.get("request_delay", _REQUEST_DELAY)
    enabled_sources = rss_cfg.get("sources")
    session = requests.Session()
    session.headers.update(_RSS_HEADERS)
    total_new = 0
    mongo_inserted = 0

    for source in ALL_RSS_SOURCES:
        if enabled_sources and source["name"] not in enabled_sources:
            continue

        try:
            entries = _rss_scrape_source(source, session)
        except Exception:
            logger.exception("[%s] Scrape failed", source["name"])
            continue

        source_tag = f"rss_news:{source['name']}"
        new_entries = []
        for entry in entries:
            url = entry.get("url")
            if url and client.documents.find_one({"metadata.url": url}):
                continue
            new_entries.append(entry)

        for entry in new_entries:
            article_url = entry.get("url", "")
            full_text = fetch_full_article(article_url, session) if article_url else None
            text = full_text or entry.get("summary", "") or entry.get("title", "")
            if not text:
                continue
            if insert_or_skip(
                client,
                source=source_tag,
                title=entry.get("title", ""),
                text=text,
                url=entry.get("url"),
                metadata={
                    "source_type": "news",
                    "category": entry.get("category", "news"),
                    "published_at": entry.get("published_at"),
                    "tags": entry.get("tags", []),
                },
                config=config,
            ):
                mongo_inserted += 1

        total_new += len(new_entries)
        if new_entries:
            logger.info("[%s] %d new articles inserted", source["name"], len(new_entries))

        time.sleep(request_delay)

    logger.info(
        "RSS news scrape complete: %d new articles, %d inserted to MongoDB",
        total_new, mongo_inserted,
    )


# --- Entry point ---

def run(config: dict) -> None:
    """Unified news scraper entry point.

    Runs enabled sub-runners with a single MongoDB client:
    - config.scraping.newspapers.enabled (default True) → diaspora newspapers
    - config.scraping.eastern_armenian.enabled (default True) → EA news agencies
    - config.scraping.rss_news.enabled (default True) → RSS news feeds
    """
    from ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client is None")

        if config.get("scraping", {}).get("newspapers", {}).get("enabled", True):
            _run_newspapers(config, client)

        if config.get("scraping", {}).get("eastern_armenian", {}).get("enabled", True):
            _run_eastern_armenian(config, client)

        if config.get("scraping", {}).get("rss_news", {}).get("enabled", True):
            _run_rss_news(config, client)
