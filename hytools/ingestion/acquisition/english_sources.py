"""English-language scrapers for Armenian history and academic sources.

Dynamically discovers Armenian-related articles from English Wikipedia
categories, plus Hyestart.am and CSU Fresno Armenian Studies.

Output: MongoDB only (source="english_sources:{source_name}").
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_REQUEST_DELAY = 2.0  # polite delay between requests


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Wikipedia Armenian History pages
# ---------------------------------------------------------------------------

WIKIPEDIA_CATEGORIES: list[str] = [
    "Category:History of Armenia",
    "Category:Armenian culture",
    "Category:Armenian language",
    "Category:Armenian diaspora",
    "Category:Armenian Apostolic Church",
    "Category:Armenian genocide",
    "Category:Armenian people",
    "Category:Western Armenian language",
    "Category:Armenian literature",
    "Category:Armenian art",
    "Category:Armenian music",
]

_WIKI_API = "https://en.wikipedia.org/w/api.php"


def _discover_wikipedia_pages(
    session: requests.Session,
    max_per_category: int = 50,
    max_depth: int = 0,
) -> list[tuple[str, str]]:
    """Dynamically discover Armenian-related pages from Wikipedia categories."""
    seen_titles: set[str] = set()
    pages: list[tuple[str, str]] = []

    for category in WIKIPEDIA_CATEGORIES:
        params: dict = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "page",
            "cmlimit": str(max_per_category),
            "format": "json",
        }
        try:
            resp = session.get(_WIKI_API, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Wikipedia category query failed for %s: %s", category, exc)
            continue

        for member in data.get("query", {}).get("categorymembers", []):
            title = member.get("title", "")
            if not title or title in seen_titles:
                continue
            if title.startswith("Category:") or title.startswith("Template:"):
                continue
            seen_titles.add(title)
            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            pages.append((title, url))

        time.sleep(1)

    logger.info("Discovered %d Armenian-related Wikipedia pages from %d categories",
                len(pages), len(WIKIPEDIA_CATEGORIES))
    return pages


def _scrape_wikipedia_page(
    title: str, url: str, session: requests.Session,
) -> Optional[dict]:
    """Scrape lead + substantial paragraphs from a Wikipedia article."""
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        time.sleep(_REQUEST_DELAY)
    except requests.RequestException as exc:
        # 404, DNS failures, timeouts: log and skip so the rest of the pipeline continues
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    content_div = soup.select_one("#mw-content-text .mw-parser-output")
    if not content_div:
        return None

    # Lead paragraphs (before first h2)
    lead_parts: list[str] = []
    for el in content_div.children:
        if not isinstance(el, Tag):
            continue
        if el.name == "h2":
            break
        if el.name == "p":
            text = _clean_text(el.get_text(separator=" "))
            if len(text) > 50:
                lead_parts.append(text)

    summary = " ".join(lead_parts[:3])

    # First 20 substantial paragraphs for content
    all_paragraphs = [
        _clean_text(p.get_text(separator=" "))
        for p in content_div.find_all("p")
        if len(p.get_text(strip=True)) > 50
    ]
    content = " ".join(all_paragraphs[:20])[:5000]

    if not content:
        return None

    return {
        "title": title,
        "url": url,
        "content": content,
        "summary": summary[:800],
        "source_name": "Wikipedia Armenian History",
        "category": "history",
        "tags": ["history", "armenia", "wikipedia"],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def _scrape_wikipedia_history(session: requests.Session, max_per_category: int = 50) -> list[dict]:
    pages = _discover_wikipedia_pages(session, max_per_category=max_per_category)
    articles: list[dict] = []
    for title, url in pages:
        article = _scrape_wikipedia_page(title, url, session)
        if article:
            articles.append(article)
    logger.info("Wikipedia: collected %d articles from %d pages", len(articles), len(pages))
    return articles


# ---------------------------------------------------------------------------
# Hyestart.am cultural portal
# ---------------------------------------------------------------------------

_HYESTART_URL = "https://www.hyestart.am"


def _scrape_hyestart(session: requests.Session) -> list[dict]:
    """Scrape article links from hyestart.am."""
    try:
        resp = session.get(_HYESTART_URL, timeout=20)
        resp.raise_for_status()
        time.sleep(_REQUEST_DELAY)
    except requests.RequestException as exc:
        # DNS/unreachable: log and skip so the rest of the pipeline continues
        logger.warning("Failed to fetch hyestart.am: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    domain = _HYESTART_URL.split("//")[1].split("/")[0]
    articles: list[dict] = []

    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"])
        text = _clean_text(a_tag.get_text())
        if len(text) < 15 or len(text) > 300:
            continue
        url = href if href.startswith("http") else _HYESTART_URL + href
        if domain not in url:
            continue
        articles.append({
            "title": text,
            "url": url,
            "content": "",
            "summary": "",
            "source_name": "Hyestart",
            "category": "history",
            "tags": ["history", "armenia", "culture"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(articles) >= 20:
            break

    logger.info("Hyestart: collected %d links", len(articles))
    return articles


# ---------------------------------------------------------------------------
# CSU Fresno Armenian Studies
# ---------------------------------------------------------------------------

_CSU_FRESNO_PAGES = [
    ("history", "https://armenianstudies.csufresno.edu/history/"),
    ("culture", "https://armenianstudies.csufresno.edu/arts_and_culture/"),
]


def _scrape_csu_fresno(session: requests.Session) -> list[dict]:
    """Scrape heading/paragraph pairs from CSU Fresno Armenian Studies."""
    articles: list[dict] = []
    for category, page_url in _CSU_FRESNO_PAGES:
        try:
            resp = session.get(page_url, timeout=20)
            resp.raise_for_status()
            time.sleep(_REQUEST_DELAY)
        except requests.RequestException as exc:
            # DNS/unreachable/404: log and continue with other pages
            logger.warning("Failed to fetch %s: %s", page_url, exc)
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all(["nav", "footer", "script", "style"]):
            tag.decompose()

        for heading in soup.find_all(["h1", "h2", "h3"]):
            title = _clean_text(heading.get_text())
            if len(title) < 10:
                continue
            content_parts: list[str] = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ("h1", "h2", "h3"):
                    break
                if sibling.name == "p":
                    content_parts.append(_clean_text(sibling.get_text()))
            content = " ".join(content_parts)
            if len(content) < 100:
                continue
            articles.append({
                "title": title,
                "url": page_url,
                "content": content[:3000],
                "summary": content[:300],
                "source_name": "Armenian Studies (CSU Fresno)",
                "category": category,
                "tags": ["academia", "armenia"],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

    logger.info("CSU Fresno: collected %d academic sections", len(articles))
    return articles


# ---------------------------------------------------------------------------
# JSONL checkpoint
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(config: dict) -> None:
    """Scrape English-language Armenian history and academic sources.

    Config keys used::

        paths:
          data_root: data
        scraping:
          english_sources:
            enabled: true
            wikipedia: true
            hyestart: false   # off by default (site often unreachable)
            csu_fresno: false # off by default (site often unreachable)
            request_delay: 2.0
    """
    from hytools.ingestion._shared.helpers import open_mongodb_client, insert_or_skip
    from hytools.ingestion._shared.scraped_document import ScrapedDocument

    src_cfg = config.get("scraping", {}).get("english_sources", {})

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB connection required but unavailable")

        session = requests.Session()
        session.headers.update(_HEADERS)

        all_articles: list[dict] = []

        if src_cfg.get("wikipedia", True):
            try:
                all_articles.extend(_scrape_wikipedia_history(session))
            except Exception as exc:
                logger.warning("Wikipedia history source failed (non-fatal): %s", exc)

        if src_cfg.get("hyestart", False):
            try:
                all_articles.extend(_scrape_hyestart(session))
            except Exception as exc:
                logger.warning("Hyestart source failed (non-fatal): %s", exc)

        if src_cfg.get("csu_fresno", False):
            try:
                all_articles.extend(_scrape_csu_fresno(session))
            except Exception as exc:
                logger.warning("CSU Fresno source failed (non-fatal): %s", exc)

        mongo_inserted = 0
        skipped = 0
        for article in all_articles:
            source_tag = f"english_sources:{article.get('source_name', 'unknown')}"
            title = article.get("title", "")
            if client.documents.find_one({"source": source_tag, "title": title}):
                skipped += 1
                continue
            text = article.get("content", "") or article.get("summary", "")
            if not text:
                continue
            if insert_or_skip(
                client,
                doc=ScrapedDocument(
                    source_family=source_tag,
                    text=text,
                    title=title,
                    source_url=article.get("url"),
                    source_type="academic",
                    source_language_code="en",
                    internal_language_code="eng",
                    internal_language_branch="eng",
                    extra={
                        "category": article.get("category", ""),
                        "tags": article.get("tags", []),
                        "language": "en",
                    },
                ),
                config=config,
            ):
                mongo_inserted += 1

        logger.info(
            "English sources: %d inserted, %d duplicates skipped",
            mongo_inserted, skipped,
        )
