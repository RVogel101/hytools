"""Agos Armenian newspaper — full crawler for agos.com.tr/am.

Agos is a bilingual (Armenian/Turkish) weekly newspaper published in Istanbul.
The Armenian section (agos.com.tr/am) publishes Western Armenian content
across 10 categories: Turkey, Armenia, World, Armenian Society, Art & Culture,
Agos Daily, Life, Contemporary, Human Rights, Faces & Stories.

Strategy:
  - Crawl all category pages with ?p=N pagination (no Selenium required)
  - Extract article URLs (/am/news/..., /am/hvotvadzi/...)
  - Fetch each article and extract content from .content p
  - Classify dialect and insert into MongoDB

Entry point: run(config)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 2.5       # seconds between requests
_MIN_BODY_CHARS = 200      # discard pages with less body text
_FETCH_TIMEOUT = 20

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_BASE_URL = "https://www.agos.com.tr"

# Armenian category paths (slug-categoryId)
_CATEGORIES = [
    "tvwrkia-147",                  # Turkey
    "hahasdan-146",                 # Armenia
    "ashkharh-145",                 # World
    "hah-hasaragvwtiwn-31",         # Armenian Society
    "arvwysd-yw-mshagvht-33",      # Art & Culture
    "agosi-oragarki-30",           # Agos Daily
    "gyntsagh-141",                # Life
    "jamanagin-142",               # Contemporary
    "martgahin-irawvwnknyr-143",   # Human Rights
    "temkyr-badmvwtiwnnyr-144",    # Faces & Stories
]

# URL patterns that indicate article pages (not category/index pages)
# e.g. /am/news/artarvwtiwni-badant-kaghakaganvwtyan-39809
_ARTICLE_PATH_RE = re.compile(r"^/am/(news|hvotvadzi)/.+-\d+$")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _fetch(session: requests.Session, url: str) -> Optional[str]:
    try:
        resp = session.get(url, timeout=_FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.debug("Agos fetch failed %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Article URL discovery
# ---------------------------------------------------------------------------

def _extract_article_links(html: str) -> set[str]:
    """Extract article URLs from a listing/category page."""
    soup = BeautifulSoup(html, "lxml")
    urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if _ARTICLE_PATH_RE.match(href):
            urls.add(f"{_BASE_URL}{href}")
    return urls


def _discover_articles(
    session: requests.Session,
    already_scraped: set[str],
    max_pages_per_cat: int,
) -> set[str]:
    """Crawl all category pages to discover article URLs."""
    all_urls: set[str] = set()

    # Also scrape the main /am/ and /am/news pages
    for seed_path in ["/am", "/am/news"]:
        seed_url = f"{_BASE_URL}{seed_path}"
        html = _fetch(session, seed_url)
        if html:
            found = _extract_article_links(html) - already_scraped
            all_urls.update(found)
            logger.info("Agos: %s — %d articles", seed_path, len(found))
        time.sleep(_REQUEST_DELAY)

    # Crawl each category with pagination
    for cat_slug in _CATEGORIES:
        page = 1
        cat_total = 0
        while page <= max_pages_per_cat:
            cat_url = f"{_BASE_URL}/am/category/{cat_slug}"
            if page > 1:
                cat_url += f"?p={page}"

            html = _fetch(session, cat_url)
            if not html:
                time.sleep(_REQUEST_DELAY)
                break
            time.sleep(_REQUEST_DELAY)

            found = _extract_article_links(html) - already_scraped - all_urls
            if not found:
                logger.info(
                    "Agos: %s p=%d — no new articles, stopping",
                    cat_slug, page,
                )
                break

            all_urls.update(found)
            cat_total += len(found)
            page += 1

        if cat_total:
            logger.info("Agos: %s — %d articles across %d pages", cat_slug, cat_total, page - 1)

    logger.info("Agos: discovery complete — %d article URLs", len(all_urls))
    return all_urls


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _extract_article_content(html: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (title, body_text) from an Agos article page."""
    soup = BeautifulSoup(html, "lxml")

    # Remove boilerplate
    for tag in soup.select("script, style, nav, header, footer, aside, .ads--before-content"):
        tag.decompose()

    # Title
    title: Optional[str] = None
    h1 = soup.select_one("h1")
    if h1:
        title = h1.get_text(" ", strip=True) or None

    # Body — Agos uses .content-part .content or .content
    body: Optional[str] = None
    for sel in (".content-part .content", ".content", "section.news-single", "article"):
        container = soup.select_one(sel)
        if not isinstance(container, Tag):
            continue
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in container.find_all(["p", "li", "blockquote"])
            if len(p.get_text(strip=True)) >= 15
        ]
        candidate = "\n\n".join(paragraphs).strip()
        if len(candidate) >= _MIN_BODY_CHARS:
            body = candidate
            break

    return title, body


# ---------------------------------------------------------------------------
# Dialect classification
# ---------------------------------------------------------------------------

def _classify(text: str) -> tuple[str, float]:
    """Return (language_code, wa_score).  'hyw' for WA, 'hye' for EA."""
    try:
        from ingestion._shared.helpers import compute_wa_score, WA_SCORE_THRESHOLD
        score = compute_wa_score(text[:6000])
        lc = "hyw" if score >= WA_SCORE_THRESHOLD else "hye"
        return lc, score
    except ImportError:
        return "hyw", 0.0


# ---------------------------------------------------------------------------
# MongoDB resume helper
# ---------------------------------------------------------------------------

def _already_scraped_urls(client, source_prefix: str) -> set[str]:
    """Load URLs already in MongoDB for this source prefix (for resume)."""
    seen: set[str] = set()
    if client is None:
        return seen
    try:
        for doc in client.documents.find(
            {"source": {"$regex": f"^{source_prefix}"}},
            {"metadata.url": 1},
        ):
            url = (doc.get("metadata") or {}).get("url")
            if url:
                seen.add(url)
    except Exception as exc:
        logger.warning("Agos: could not load scraped URLs from MongoDB: %s", exc)
    return seen


# ---------------------------------------------------------------------------
# Main scrape loop
# ---------------------------------------------------------------------------

def _scrape_agos(
    session: requests.Session,
    client,
    config: dict,
) -> dict:
    """Scrape all Agos Armenian articles and insert into MongoDB."""
    from ingestion._shared.helpers import insert_or_skip

    stats = {
        "discovered": 0, "inserted": 0, "skipped": 0,
        "failed": 0, "wa": 0, "ea": 0,
    }
    source_tag = "agos"

    already_scraped = _already_scraped_urls(client, source_tag)
    logger.info("Agos: %d already-scraped URLs loaded (resume)", len(already_scraped))

    agos_cfg = (config.get("scraping") or {}).get("agos") or {}
    max_pages = int(agos_cfg.get("max_pages_per_category", 50))

    article_urls = _discover_articles(session, already_scraped, max_pages)
    logger.info("Agos: %d article URLs to scrape", len(article_urls))

    for article_url in sorted(article_urls):
        stats["discovered"] += 1

        html = _fetch(session, article_url)
        if not html:
            stats["failed"] += 1
            time.sleep(_REQUEST_DELAY)
            continue
        time.sleep(_REQUEST_DELAY)

        title, body = _extract_article_content(html)
        if not body:
            stats["skipped"] += 1
            continue

        detected_lc, wa_score = _classify(body)
        if detected_lc == "hyw":
            stats["wa"] += 1
        else:
            stats["ea"] += 1

        meta = {
            "source_type": "newspaper",
            "language_code": detected_lc,
            "source_language_codes": [detected_lc],
            "wa_score": round(wa_score, 2),
            "content_type": "article",
            "writing_category": "diaspora",
        }

        if insert_or_skip(
            client,
            source=source_tag,
            title=title or article_url.rsplit("/", 1)[-1] or article_url,
            text=body,
            url=article_url,
            metadata=meta,
            config=config,
        ):
            stats["inserted"] += 1
            if stats["inserted"] % 100 == 0:
                logger.info(
                    "Agos: %d inserted (WA=%d EA=%d)",
                    stats["inserted"], stats["wa"], stats["ea"],
                )

    logger.info(
        "Agos complete: discovered=%d inserted=%d skipped=%d failed=%d wa=%d ea=%d",
        stats["discovered"], stats["inserted"], stats["skipped"],
        stats["failed"], stats["wa"], stats["ea"],
    )
    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(config: dict) -> None:
    """Scrape Agos Armenian newspaper into MongoDB.

    Config keys (under scraping.agos):
      max_pages_per_category (int, default 50): max pagination depth per category
    """
    from ingestion._shared.helpers import open_mongodb_client

    session = _make_session()

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client required for Agos scraper")

        logger.info("=== Agos Armenian Newspaper (agos.com.tr/am) ===")
        stats = _scrape_agos(session, client, config)
        logger.info("Agos final: %s", stats)
