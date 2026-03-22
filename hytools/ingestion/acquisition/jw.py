"""JW.org Armenian-language corpus scraper (via Watchtower Online Library).

Scrapes Western Armenian (hyw) and Eastern Armenian (hy) publications from
wol.jw.org (Watchtower Online Library) and inserts into MongoDB.  Every
document is dialect-classified via compute_wa_score regardless of the source
URL's language tag — metadata.language_code is derived from the text, not
trusted from the URL.

www.jw.org blocks automated HTTP clients (returns 0 bytes after TLS).
wol.jw.org serves the same publications and is accessible.

Language coverage on WOL:
  - https://wol.jw.org/hyw/  (Western Armenian, region r487, prefix lp-r)
  - https://wol.jw.org/hy/   (Eastern Armenian, region r44, prefix lp-rea)

Both variants are scraped and kept.  EA content is tagged language_code='hye',
WA content is tagged 'hyw', based on classifier output.  The original URL
language hint is stored in metadata.url_lang for traceability.

Entry point: run(config)
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 3.0        # seconds between requests (respectful crawling)
_MIN_BODY_CHARS = 250       # discard pages with less body text than this
_FETCH_TIMEOUT = 45         # WOL responses are slow (8-28 s typical)
_MAX_CATEGORY_DEPTH = 4     # max recursion depth for category listings

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}

# WOL publication category IDs (shared across languages)
_CATEGORY_IDS = [
    73,     # Watchtower
    5309,   # Awake!
    5461,   # Books
    10232,  # Brochures
    10274,  # Tracts
    10330,  # Article Series
    10339,  # Guidelines
    5494,   # Meeting Workbook
    7127,   # Kingdom Ministry
]


@dataclass(frozen=True)
class _WolLang:
    """WOL language configuration."""
    code: str           # URL path language (hyw or hy)
    region: str         # WOL region code
    lang_prefix: str    # WOL language prefix

    @property
    def base(self) -> str:
        return f"https://wol.jw.org/{self.code}/"

    def category_url(self, cat_id: int) -> str:
        return (
            f"https://wol.jw.org/{self.code}/wol/lv/"
            f"{self.region}/{self.lang_prefix}/0/{cat_id}"
        )

    def is_document_url(self, url: str) -> bool:
        return f"/wol/d/{self.region}/{self.lang_prefix}/" in url

    def is_listing_url(self, url: str) -> bool:
        return (
            f"/wol/lv/{self.region}/{self.lang_prefix}/" in url
            or f"/wol/publication/{self.region}/{self.lang_prefix}/" in url
        )


_WOL_HYW = _WolLang(code="hyw", region="r487", lang_prefix="lp-r")
_WOL_HY  = _WolLang(code="hy",  region="r44",  lang_prefix="lp-rea")


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
        logger.debug("WOL fetch failed %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------

def _extract_wol_links(
    html: str, page_url: str, wol: _WolLang,
) -> tuple[set[str], set[str]]:
    """Return (document_urls, sub-listing_urls) found on a WOL page."""
    soup = BeautifulSoup(html, "lxml")
    docs: set[str] = set()
    listings: set[str] = set()
    prefix = f"https://wol.jw.org/{wol.code}/"

    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        absolute = urljoin(page_url, href).split("?")[0].split("#")[0]
        if not absolute.startswith(prefix):
            continue
        if wol.is_document_url(absolute):
            docs.add(absolute)
        elif wol.is_listing_url(absolute) and absolute != page_url:
            listings.add(absolute)

    return docs, listings


# ---------------------------------------------------------------------------
# Discovery (BFS over category listings)
# ---------------------------------------------------------------------------

def _discover_documents(
    session: requests.Session,
    wol: _WolLang,
    already_scraped: set[str],
) -> set[str]:
    """BFS-crawl WOL category listings to discover document URLs."""
    all_docs: set[str] = set()
    visited: set[str] = set()

    queue: deque[tuple[str, int]] = deque(
        (wol.category_url(cid), 0) for cid in _CATEGORY_IDS
    )

    while queue:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        logger.info(
            "WOL/%s: listing [d=%d, visited=%d, docs=%d] %s",
            wol.code, depth, len(visited), len(all_docs), url,
        )

        html = _fetch(session, url)
        if not html:
            time.sleep(_REQUEST_DELAY)
            continue
        time.sleep(_REQUEST_DELAY)

        doc_urls, sub_listings = _extract_wol_links(html, url, wol)
        new_docs = doc_urls - already_scraped
        all_docs.update(new_docs)
        if new_docs:
            logger.info(
                "WOL/%s: +%d documents from %s",
                wol.code, len(new_docs), url,
            )

        if depth < _MAX_CATEGORY_DEPTH:
            for sub in sub_listings:
                if sub not in visited:
                    queue.append((sub, depth + 1))

    logger.info(
        "WOL/%s: discovery complete — %d listings crawled, %d documents found",
        wol.code, len(visited), len(all_docs),
    )
    return all_docs


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _extract_article_content(html: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (title, body_text) from a WOL document page."""
    soup = BeautifulSoup(html, "lxml")

    # Remove boilerplate
    for tag in soup.select("script, style, nav, header, footer, aside"):
        tag.decompose()

    # Title — prefer heading inside <article>
    title: Optional[str] = None
    article = soup.select_one("article")
    if isinstance(article, Tag):
        for sel in ("h1", "h2", ".contextTitle"):
            node = article.select_one(sel)
            if node:
                title = node.get_text(" ", strip=True) or None
                if title:
                    break
    if not title:
        node = soup.select_one("h1") or soup.select_one("title")
        if node:
            title = node.get_text(" ", strip=True) or None

    # Body — extract from <article> first
    body: Optional[str] = None
    if isinstance(article, Tag):
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in article.find_all(["p", "li", "blockquote"])
            if len(p.get_text(strip=True)) >= 20
        ]
        candidate = "\n\n".join(paragraphs).strip()
        if len(candidate) >= _MIN_BODY_CHARS:
            body = candidate

    if not body:
        # Fallback: all paragraphs in document
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) >= 20
        ]
        candidate = "\n\n".join(paragraphs).strip()
        if len(candidate) >= _MIN_BODY_CHARS:
            body = candidate

    return title, body


# ---------------------------------------------------------------------------
# Dialect classification
# ---------------------------------------------------------------------------

def _classify(text: str) -> tuple[str, float]:
    """Return (language_code, wa_score).  'hyw' for WA, 'hye' for EA."""
    try:
        from hytools.ingestion._shared.helpers import compute_wa_score, WA_SCORE_THRESHOLD
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
        logger.warning("WOL: could not load scraped URLs from MongoDB: %s", exc)
    return seen


# ---------------------------------------------------------------------------
# Per-language scrape loop
# ---------------------------------------------------------------------------

def _scrape_wol_lang(
    wol: _WolLang,
    session: requests.Session,
    client,
    config: dict,
) -> dict:
    """Scrape all WOL publications for one language and insert into MongoDB."""
    from hytools.ingestion._shared.helpers import insert_or_skip

    stats = {
        "discovered": 0, "inserted": 0, "skipped": 0,
        "failed": 0, "wa": 0, "ea": 0,
    }
    source_tag = f"jw_org:{wol.code}"

    already_scraped = _already_scraped_urls(client, source_tag)
    logger.info(
        "WOL/%s: %d already-scraped URLs loaded (resume)", wol.code, len(already_scraped),
    )

    doc_urls = _discover_documents(session, wol, already_scraped)
    logger.info("WOL/%s: %d document URLs discovered", wol.code, len(doc_urls))

    for doc_url in sorted(doc_urls):
        stats["discovered"] += 1

        if doc_url in already_scraped:
            stats["skipped"] += 1
            continue

        html = _fetch(session, doc_url)
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
            "source_type": "religious",
            "source_language_code": detected_lc,
            "source_language_codes": [detected_lc],
            "wa_score": round(wa_score, 2),
            "url_lang": wol.code,
            "content_type": "article",
            "writing_category": "religious",
        }

        if insert_or_skip(
            client,
            source=source_tag,
            title=title or doc_url.rsplit("/", 1)[-1] or doc_url,
            text=body,
            url=doc_url,
            metadata=meta,
            config=config,
        ):
            stats["inserted"] += 1
            if stats["inserted"] % 100 == 0:
                logger.info(
                    "WOL/%s: %d inserted (WA=%d EA=%d)",
                    wol.code, stats["inserted"], stats["wa"], stats["ea"],
                )

    logger.info(
        "WOL/%s complete: discovered=%d inserted=%d skipped=%d failed=%d wa=%d ea=%d",
        wol.code, stats["discovered"], stats["inserted"], stats["skipped"],
        stats["failed"], stats["wa"], stats["ea"],
    )
    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(config: dict) -> None:
    """Scrape WA and EA publications from wol.jw.org into MongoDB.

    Config keys (under scraping.jw):
      include_eastern (bool, default True): also scrape hy (Eastern Armenian)
    """
    from hytools.ingestion._shared.helpers import open_mongodb_client

    jw_cfg = (config.get("scraping") or {}).get("jw") or {}
    include_ea = bool(jw_cfg.get("include_eastern", True))

    session = _make_session()

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client required for JW.org scraper")

        logger.info("=== WOL Western Armenian (hyw) — r487/lp-r ===")
        wa_stats = _scrape_wol_lang(_WOL_HYW, session, client, config)
        logger.info("WOL hyw final: %s", wa_stats)

        if include_ea:
            logger.info("=== WOL Eastern Armenian (hy) — r44/lp-rea ===")
            ea_stats = _scrape_wol_lang(_WOL_HY, session, client, config)
            logger.info("WOL hy final: %s", ea_stats)
