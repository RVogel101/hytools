"""JW.org Armenian-language corpus scraper.

Scrapes Western Armenian (hyw) and Eastern Armenian (hy) publications from
jw.org and inserts into MongoDB. Every document is dialect-classified via
compute_wa_score regardless of the source URL's language tag — the
metadata.language_code is derived from the text, not trusted from the URL.

Language coverage:
  - https://www.jw.org/hyw/  (hyw in URL, Western Armenian)
  - https://www.jw.org/hy/   (hy in URL, Eastern Armenian)

Both variants are scraped and kept.  EA content is tagged language_code='hye',
WA content is tagged 'hyw', based on classifier output.  The original URL
language hint is stored in metadata.url_lang for traceability.

Entry point: run(config)
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 2.5  # seconds between requests (respectful crawling)
_MIN_BODY_CHARS = 250   # discard pages with less body text than this
_MAX_DEPTH = 2          # crawl depth: library index → publication → chapter

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Top-level library sections to crawl per language variant
_LIBRARY_SECTIONS = [
    "library/books/",
    "library/magazines/",
    "library/videos/",
    "library/bible/",
    "news/",
    "jehovahs-witnesses/",
]

# URL path segments that indicate a navigation/index page, not an article
_INDEX_SUFFIXES = (
    "/library/",
    "/books/",
    "/magazines/",
    "/bible/",
    "/videos/",
    "/news/",
    "/jehovahs-witnesses/",
    "/search/",
    "/rss/",
    "/sitemap",
)

# Minimum path depth for a URL to be considered an article
_MIN_PATH_DEPTH = 3   # e.g. /hyw/library/books/... has depth ≥ 3


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _fetch(session: requests.Session, url: str, timeout: int = 20) -> Optional[str]:
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.debug("JW.org fetch failed %s: %s", url, exc)
        return None


def _is_article_url(url: str, base_url: str) -> bool:
    """Return True if url looks like a leaf article (not a navigation/index page)."""
    if not url.startswith(base_url):
        return False
    path = urlparse(url).path.rstrip("/")
    depth = path.count("/")
    if depth < _MIN_PATH_DEPTH:
        return False
    if url.endswith(_INDEX_SUFFIXES):
        return False
    # Fragment-only or query-parameter URLs
    parsed = urlparse(url)
    if parsed.fragment and not parsed.path:
        return False
    return True


def _extract_links(html: str, base_url: str, page_url: str) -> list[str]:
    """Extract all candidate article/publication links from an HTML page."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        absolute = urljoin(page_url, href).split("?")[0].split("#")[0]
        if absolute in seen:
            continue
        if not absolute.startswith(base_url):
            continue
        seen.add(absolute)
        links.append(absolute)

    return links


def _extract_article_content(html: str, url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (title, body_text) from a JW.org article page.

    Tries JW.org-specific selectors first, then falls back to generic paragraph extraction.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove boilerplate
    for tag in soup.select("script, style, nav, header, footer, aside, .shareLinks, .relatedItems, .synopsis"):
        tag.decompose()

    # Title
    title: Optional[str] = None
    for sel in ["#article h1", ".title h1", "h1.title", "h1", ".pageTitle", "title"]:
        node = soup.select_one(sel)
        if node:
            title = node.get_text(" ", strip=True) or None
            if title:
                break

    # Body — JW.org article containers (ordered by specificity)
    body_selectors = [
        "#article .bodyTxt",
        ".body-content",
        "#article",
        ".articleBody",
        ".bodyText",
        "article .body",
        "article",
        "main",
    ]

    body: Optional[str] = None
    for sel in body_selectors:
        container = soup.select_one(sel)
        if not isinstance(container, Tag):
            continue
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in container.find_all(["p", "li", "blockquote"])
            if len(p.get_text(strip=True)) >= 20
        ]
        candidate = "\n\n".join(paragraphs).strip()
        if len(candidate) >= _MIN_BODY_CHARS:
            body = candidate
            break

    if not body:
        # Generic fallback: all paragraphs in document
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) >= 20
        ]
        candidate = "\n\n".join(paragraphs).strip()
        if len(candidate) >= _MIN_BODY_CHARS:
            body = candidate

    return title, body


def _classify(text: str) -> tuple[str, float]:
    """Classify text dialect. Returns (language_code, wa_score).

    Uses the canonical compute_wa_score from ingestion._shared.helpers.
    language_code is 'hyw' for WA, 'hye' for EA.
    """
    try:
        from ingestion._shared.helpers import compute_wa_score, WA_SCORE_THRESHOLD
        score = compute_wa_score(text[:6000])
        lc = "hyw" if score >= WA_SCORE_THRESHOLD else "hye"
        return lc, score
    except ImportError:
        return "hyw", 0.0


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
        logger.warning("JW.org: could not load scraped URLs from MongoDB: %s", exc)
    return seen


def _discover_article_urls(
    session: requests.Session,
    lang_code: str,
    base_url: str,
    already_scraped: set[str],
) -> set[str]:
    """Crawl library sections two levels deep to discover all article URLs."""
    all_urls: set[str] = set()

    for section in _LIBRARY_SECTIONS:
        section_url = urljoin(base_url, section)
        logger.info("JW.org/%s: crawling section %s", lang_code, section_url)

        html = _fetch(session, section_url)
        if not html:
            time.sleep(_REQUEST_DELAY)
            continue
        time.sleep(_REQUEST_DELAY)

        depth1_links = _extract_links(html, base_url, section_url)
        depth1_articles = [l for l in depth1_links if _is_article_url(l, base_url)]
        depth1_index = [l for l in depth1_links if not _is_article_url(l, base_url) and l.startswith(base_url)]

        for url in depth1_articles:
            all_urls.add(url)

        # Go one level deeper (publication index → chapters/articles)
        crawled = 0
        for pub_url in depth1_index:
            if crawled >= 500:  # safety cap per section
                break
            if pub_url in already_scraped:
                continue
            pub_html = _fetch(session, pub_url)
            if not pub_html:
                time.sleep(_REQUEST_DELAY)
                continue
            time.sleep(_REQUEST_DELAY)

            for link in _extract_links(pub_html, base_url, pub_url):
                if _is_article_url(link, base_url):
                    all_urls.add(link)
            crawled += 1

        logger.info(
            "JW.org/%s %s: %d total article URLs so far",
            lang_code, section, len(all_urls),
        )

    return all_urls


def _scrape_jw_lang(
    lang_code: str,
    base_url: str,
    session: requests.Session,
    client,
    config: dict,
) -> dict:
    """Scrape all publications for one JW.org language variant and insert into MongoDB."""
    from ingestion._shared.helpers import insert_or_skip

    stats = {"discovered": 0, "inserted": 0, "skipped": 0, "failed": 0, "wa": 0, "ea": 0}
    source_tag = f"jw_org:{lang_code}"

    already_scraped = _already_scraped_urls(client, source_tag)
    logger.info("JW.org/%s: %d already-scraped URLs loaded (resume)", lang_code, len(already_scraped))

    article_urls = _discover_article_urls(session, lang_code, base_url, already_scraped)
    logger.info("JW.org/%s: %d article URLs discovered", lang_code, len(article_urls))

    for article_url in sorted(article_urls):
        stats["discovered"] += 1

        if article_url in already_scraped:
            stats["skipped"] += 1
            continue

        html = _fetch(session, article_url)
        if not html:
            stats["failed"] += 1
            time.sleep(_REQUEST_DELAY)
            continue
        time.sleep(_REQUEST_DELAY)

        title, body = _extract_article_content(html, article_url)
        if not body:
            stats["skipped"] += 1
            continue

        # Classify dialect from actual text content — do NOT trust the URL lang tag
        detected_lc, wa_score = _classify(body)
        dialect = "western_armenian" if detected_lc == "hyw" else "eastern_armenian"

        if detected_lc == "hyw":
            stats["wa"] += 1
        else:
            stats["ea"] += 1

        meta = {
            "source_type": "religious",
            "language_code": detected_lc,
            "dialect": dialect,
            "source_language_codes": [detected_lc],
            "wa_score": round(wa_score, 2),
            "url_lang": lang_code,   # original JW.org URL language hint (for traceability)
            "content_type": "article",
            "writing_category": "religious",
        }

        if insert_or_skip(
            client,
            source=source_tag,
            title=title or article_url.split("/")[-1] or article_url,
            text=body,
            url=article_url,
            metadata=meta,
            config=config,
        ):
            stats["inserted"] += 1
            if stats["inserted"] % 200 == 0:
                logger.info(
                    "JW.org/%s: %d inserted (WA=%d EA=%d)",
                    lang_code, stats["inserted"], stats["wa"], stats["ea"],
                )

    logger.info(
        "JW.org/%s complete: discovered=%d inserted=%d skipped=%d failed=%d wa=%d ea=%d",
        lang_code, stats["discovered"], stats["inserted"], stats["skipped"],
        stats["failed"], stats["wa"], stats["ea"],
    )
    return stats


def run(config: dict) -> None:
    """Entry point: scrape WA and EA JW.org content into MongoDB.

    Config keys (under scraping.jw):
      include_eastern (bool, default True): also scrape hy (Eastern Armenian) variant
    """
    from ingestion._shared.helpers import open_mongodb_client

    jw_cfg = (config.get("scraping") or {}).get("jw") or {}
    include_ea = bool(jw_cfg.get("include_eastern", True))

    session = _make_session()

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client required for JW.org scraper")

        logger.info("=== JW.org Western Armenian (hyw) ===")
        wa_stats = _scrape_jw_lang("hyw", "https://www.jw.org/hyw/", session, client, config)
        logger.info("JW.org hyw final: %s", wa_stats)

        if include_ea:
            logger.info("=== JW.org Eastern Armenian (hy) ===")
            ea_stats = _scrape_jw_lang("hy", "https://www.jw.org/hy/", session, client, config)
            logger.info("JW.org hy final: %s", ea_stats)
