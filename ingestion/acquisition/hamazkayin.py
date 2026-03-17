"""Hamazkayin Armenian Cultural Organization — scraper for pakine.net + hamazkayin.com.

Hamazkayin publishes books, journals, plays, and poetry in Western Armenian.
Pakine (Բագին) is their flagship literary magazine with full articles online.

Sources:
  - pakine.net   — literary magazine: prose, poetry, criticism, interviews, translations
  - hamazkayin.com — news articles, cultural event coverage, author profiles

Both sites are WordPress-based. We prefer the WP REST API (wp-json/wp/v2/posts)
for structured access; fall back to HTML scraping if the API is unavailable.

Entry point: run(config)
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 3.0  # seconds between requests
_MIN_BODY_CHARS = 200
_WP_API_PER_PAGE = 100  # max posts per page in WP REST API

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Sites to scrape — order: pakine first (higher-value literary content)
_SITES = [
    {
        "name": "pakine",
        "base_url": "https://pakine.net",
        "wp_api": "https://pakine.net/wp-json/wp/v2/posts",
        "wp_endpoints": ["posts"],  # pages API broken, authors have 0 content
        "source_tag": "hamazkayin:pakine",
        "writing_category": "literary",
        "content_type": "article",
    },
    {
        "name": "hamazkayin",
        "base_url": "https://hamazkayin.com",
        "wp_api": "https://hamazkayin.com/wp-json/wp/v2/posts",
        "wp_endpoints": ["posts", "pages"],  # 108 pages with cultural content
        "source_tag": "hamazkayin:main",
        "writing_category": "cultural",
        "content_type": "article",
    },
]


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _classify(text: str) -> tuple[str, float]:
    """Classify text dialect. Returns (language_code, wa_score)."""
    try:
        from ingestion._shared.helpers import compute_wa_score, WA_SCORE_THRESHOLD
        score = compute_wa_score(text[:6000])
        lc = "hyw" if score >= WA_SCORE_THRESHOLD else "hye"
        return lc, score
    except ImportError:
        return "hyw", 0.0


def _html_to_text(html_content: str) -> str:
    """Convert HTML content (from WP API rendered field) to clean text.

    Tries structured extraction (p/li/blockquote/h*) first, then falls back
    to full ``get_text()`` for posts that wrap content in <div>/<span>/<table>.
    """
    soup = BeautifulSoup(html_content, "lxml")
    for tag in soup.select("script, style, nav, header, footer, aside"):
        tag.decompose()

    # 1. Structured extraction — clean paragraphs from semantic tags
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in soup.find_all(["p", "li", "blockquote", "h2", "h3", "h4"])
        if len(p.get_text(strip=True)) >= 15
    ]
    body = "\n\n".join(paragraphs).strip()
    if len(body) >= _MIN_BODY_CHARS:
        return body

    # 2. Fallback — full text extraction for <div>/<span>/<table> layouts
    import re
    full = soup.get_text("\n", strip=True)
    # Collapse blank lines
    full = re.sub(r"\n{3,}", "\n\n", full).strip()
    return full


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
        logger.warning("Hamazkayin: could not load scraped URLs: %s", exc)
    return seen


def _scrape_via_wp_api(
    session: requests.Session,
    site: dict,
    client,
    config: dict,
    already_scraped: set[str],
) -> dict:
    """Scrape all posts (and pages if configured) via WordPress REST API. Returns stats dict."""
    from ingestion._shared.helpers import insert_or_skip

    stats = {"discovered": 0, "inserted": 0, "skipped": 0, "failed": 0, "wa": 0, "ea": 0}
    base_api = site["base_url"] + "/wp-json/wp/v2"
    endpoints = site.get("wp_endpoints", ["posts"])

    for endpoint in endpoints:
        api_url = f"{base_api}/{endpoint}"
        page = 1
        logger.info("Hamazkayin/%s: scraping WP endpoint '%s'", site["name"], endpoint)

        while True:
            params = {"per_page": _WP_API_PER_PAGE, "page": page, "orderby": "date", "order": "asc"}
            try:
                resp = session.get(api_url, params=params, timeout=30)
                if resp.status_code == 400:
                    logger.info("Hamazkayin/%s/%s: API returned 400 at page %d — end", site["name"], endpoint, page)
                    break
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("Hamazkayin/%s/%s: API request failed at page %d: %s", site["name"], endpoint, page, exc)
                break

            posts = resp.json()
            if not isinstance(posts, list) or not posts:
                logger.info("Hamazkayin/%s/%s: no more items at page %d", site["name"], endpoint, page)
                break

            for post in posts:
                stats["discovered"] += 1
                url = post.get("link", "")

                if url in already_scraped:
                    stats["skipped"] += 1
                    continue

                # Extract text from rendered content
                content_html = (post.get("content") or {}).get("rendered", "")
                body = _html_to_text(content_html)
                if len(body) < _MIN_BODY_CHARS:
                    stats["skipped"] += 1
                    continue

                title = BeautifulSoup(
                    (post.get("title") or {}).get("rendered", ""), "html.parser"
                ).get_text(strip=True) or url.split("/")[-2] or url

                detected_lc, wa_score = _classify(body)
                if detected_lc == "hyw":
                    stats["wa"] += 1
                else:
                    stats["ea"] += 1

                meta = {
                    "source_type": "literary" if site["name"] == "pakine" else "cultural",
                    "source_language_code": detected_lc,
                    "source_language_codes": [detected_lc],
                    "wa_score": round(wa_score, 2),
                    "content_type": site["content_type"],
                    "writing_category": site["writing_category"],
                    "published_at": post.get("date"),
                    "wp_type": endpoint,
                }

                if insert_or_skip(
                    client,
                    source=site["source_tag"],
                    title=title,
                    text=body,
                    url=url,
                    metadata=meta,
                    config=config,
                ):
                    stats["inserted"] += 1
                    if stats["inserted"] % 100 == 0:
                        logger.info(
                            "Hamazkayin/%s: %d inserted (WA=%d EA=%d)",
                            site["name"], stats["inserted"], stats["wa"], stats["ea"],
                        )

            logger.info(
                "Hamazkayin/%s/%s: page %d — %d items fetched, total inserted so far: %d",
                site["name"], endpoint, page, len(posts), stats["inserted"],
            )
            page += 1
            time.sleep(_REQUEST_DELAY)

    return stats


def _scrape_via_html_fallback(
    session: requests.Session,
    site: dict,
    client,
    config: dict,
    already_scraped: set[str],
) -> dict:
    """Fallback HTML scraper if WP REST API is unavailable."""
    from ingestion._shared.helpers import insert_or_skip

    stats = {"discovered": 0, "inserted": 0, "skipped": 0, "failed": 0, "wa": 0, "ea": 0}
    base_url = site["base_url"]
    page = 1
    max_pages = 500

    while page <= max_pages:
        listing_url = f"{base_url}/page/{page}/"
        try:
            resp = session.get(listing_url, timeout=20)
            if resp.status_code == 404:
                logger.info("Hamazkayin/%s: 404 at page %d — end of pages", site["name"], page)
                break
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Hamazkayin/%s: listing page %d failed: %s", site["name"], page, exc)
            break

        soup = BeautifulSoup(resp.text, "lxml")
        links: list[str] = []
        for a in soup.select("h2 a, .entry-title a, .post-title a, article a"):
            href = a.get("href")
            if isinstance(href, str) and href.startswith(base_url):
                if href not in already_scraped and href not in links:
                    links.append(href)

        if not links:
            logger.info("Hamazkayin/%s: no links on page %d — stopping", site["name"], page)
            break

        for article_url in links:
            stats["discovered"] += 1

            if article_url in already_scraped:
                stats["skipped"] += 1
                continue

            time.sleep(_REQUEST_DELAY)
            try:
                art_resp = session.get(article_url, timeout=20)
                art_resp.raise_for_status()
            except requests.RequestException:
                stats["failed"] += 1
                continue

            art_soup = BeautifulSoup(art_resp.text, "lxml")
            for tag in art_soup.select("script, style, nav, header, footer, aside"):
                tag.decompose()

            # Extract body
            body = ""
            for sel in [".entry-content", ".post-content", "article .content", "article"]:
                container = art_soup.select_one(sel)
                if isinstance(container, Tag):
                    paragraphs = [
                        p.get_text(" ", strip=True)
                        for p in container.find_all(["p", "li", "blockquote"])
                        if len(p.get_text(strip=True)) >= 15
                    ]
                    candidate = "\n\n".join(paragraphs).strip()
                    if len(candidate) >= _MIN_BODY_CHARS:
                        body = candidate
                        break

            if not body:
                stats["skipped"] += 1
                continue

            # Title
            title_tag = art_soup.select_one("h1.entry-title, h1.post-title, h1, .page-title")
            title = title_tag.get_text(strip=True) if title_tag else article_url.split("/")[-2]

            detected_lc, wa_score = _classify(body)
            if detected_lc == "hyw":
                stats["wa"] += 1
            else:
                stats["ea"] += 1

            meta = {
                "source_type": "literary" if site["name"] == "pakine" else "cultural",
                "source_language_code": detected_lc,
                "source_language_codes": [detected_lc],
                "wa_score": round(wa_score, 2),
                "content_type": site["content_type"],
                "writing_category": site["writing_category"],
            }

            if insert_or_skip(
                client,
                source=site["source_tag"],
                title=title,
                text=body,
                url=article_url,
                metadata=meta,
                config=config,
            ):
                stats["inserted"] += 1
                if stats["inserted"] % 100 == 0:
                    logger.info(
                        "Hamazkayin/%s: %d inserted (WA=%d EA=%d)",
                        site["name"], stats["inserted"], stats["wa"], stats["ea"],
                    )

        page += 1
        time.sleep(_REQUEST_DELAY)

    return stats


def _scrape_site(
    session: requests.Session,
    site: dict,
    client,
    config: dict,
) -> dict:
    """Scrape one Hamazkayin site — try WP API first, fall back to HTML."""
    already_scraped = _already_scraped_urls(client, site["source_tag"])
    logger.info(
        "Hamazkayin/%s: %d already-scraped URLs loaded (resume)",
        site["name"], len(already_scraped),
    )

    # Try WP REST API first
    try:
        test_resp = session.get(site["wp_api"], params={"per_page": 1}, timeout=15)
        if test_resp.status_code == 200 and isinstance(test_resp.json(), list):
            logger.info("Hamazkayin/%s: WP REST API available — using API scraper", site["name"])
            return _scrape_via_wp_api(session, site, client, config, already_scraped)
    except Exception as exc:
        logger.info("Hamazkayin/%s: WP REST API unavailable (%s) — falling back to HTML", site["name"], exc)

    logger.info("Hamazkayin/%s: using HTML fallback scraper", site["name"])
    return _scrape_via_html_fallback(session, site, client, config, already_scraped)


def run(config: dict) -> None:
    """Entry point: scrape Hamazkayin sites (pakine.net + hamazkayin.com) into MongoDB.

    Config keys (under scraping.hamazkayin):
      sites (list[str] | null, default null): site names to scrape. null = all.
        Examples: ["pakine"], ["pakine", "hamazkayin"]
    """
    from ingestion._shared.helpers import open_mongodb_client

    hz_cfg = (config.get("scraping") or {}).get("hamazkayin") or {}
    enabled_sites: list[str] | None = hz_cfg.get("sites")

    session = _make_session()

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client required for Hamazkayin scraper")

        for site in _SITES:
            if enabled_sites is not None and site["name"] not in enabled_sites:
                logger.info("Hamazkayin: skipping %s (not in enabled sites)", site["name"])
                continue

            logger.info("=== Hamazkayin: %s (%s) ===", site["name"], site["base_url"])
            stats = _scrape_site(session, site, client, config)
            logger.info(
                "Hamazkayin/%s complete: discovered=%d inserted=%d skipped=%d failed=%d wa=%d ea=%d",
                site["name"], stats["discovered"], stats["inserted"], stats["skipped"],
                stats["failed"], stats["wa"], stats["ea"],
            )
