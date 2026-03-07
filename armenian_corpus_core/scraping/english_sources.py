"""English-language scrapers for Armenian history and academic sources.

Fetches content from English Wikipedia Armenian history pages,
Hyestart.am cultural portal, and CSU Fresno Armenian Studies.
Adapted from ``hyebot/app/scrapers/history_journals.py``.

Output
------
Articles are written to a JSONL checkpoint file in
``<data_root>/raw/english_sources/articles.jsonl``.
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

WIKIPEDIA_HISTORY_PAGES: list[tuple[str, str]] = [
    ("History of Armenia", "https://en.wikipedia.org/wiki/History_of_Armenia"),
    ("Armenian Genocide", "https://en.wikipedia.org/wiki/Armenian_genocide"),
    ("Kingdom of Armenia (antiquity)", "https://en.wikipedia.org/wiki/Kingdom_of_Armenia_(antiquity)"),
    ("Urartu", "https://en.wikipedia.org/wiki/Urartu"),
    ("Armenian Apostolic Church", "https://en.wikipedia.org/wiki/Armenian_Apostolic_Church"),
    ("First Republic of Armenia", "https://en.wikipedia.org/wiki/First_Republic_of_Armenia"),
    ("Nagorno-Karabakh", "https://en.wikipedia.org/wiki/Nagorno-Karabakh"),
    ("Armenian diaspora", "https://en.wikipedia.org/wiki/Armenian_diaspora"),
    ("Komitas", "https://en.wikipedia.org/wiki/Komitas"),
    ("Tigran the Great", "https://en.wikipedia.org/wiki/Tigranes_the_Great"),
    ("Battle of Avarayr", "https://en.wikipedia.org/wiki/Battle_of_Avarayr"),
    ("Mesrop Mashtots", "https://en.wikipedia.org/wiki/Mesrop_Mashtots"),
    ("Mount Ararat in Armenian culture", "https://en.wikipedia.org/wiki/Mount_Ararat_in_Armenian_culture"),
    ("Treaty of Sevres", "https://en.wikipedia.org/wiki/Treaty_of_S%C3%A8vres"),
    ("Cilician Armenia", "https://en.wikipedia.org/wiki/Armenian_Kingdom_of_Cilicia"),
]


def _scrape_wikipedia_page(
    title: str, url: str, session: requests.Session,
) -> Optional[dict]:
    """Scrape lead + substantial paragraphs from a Wikipedia article."""
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        time.sleep(_REQUEST_DELAY)
    except requests.RequestException as exc:
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


def _scrape_wikipedia_history(session: requests.Session) -> list[dict]:
    articles: list[dict] = []
    for title, url in WIKIPEDIA_HISTORY_PAGES:
        article = _scrape_wikipedia_page(title, url, session)
        if article:
            articles.append(article)
    logger.info("Wikipedia History: collected %d articles", len(articles))
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
            hyestart: true
            csu_fresno: true
            request_delay: 2.0
    """
    paths = config.get("paths", {})
    data_root = Path(paths.get("data_root", "data"))
    src_cfg = config.get("scraping", {}).get("english_sources", {})

    request_delay = src_cfg.get("request_delay", _REQUEST_DELAY)

    output_dir = data_root / "raw" / "english_sources"
    jsonl_path = output_dir / "articles.jsonl"
    existing_urls = _load_existing_urls(jsonl_path)

    session = requests.Session()
    session.headers.update(_HEADERS)

    all_articles: list[dict] = []

    if src_cfg.get("wikipedia", True):
        all_articles.extend(_scrape_wikipedia_history(session))

    if src_cfg.get("hyestart", True):
        all_articles.extend(_scrape_hyestart(session))

    if src_cfg.get("csu_fresno", True):
        all_articles.extend(_scrape_csu_fresno(session))

    # Deduplicate against existing checkpoint
    new_articles = [a for a in all_articles if a.get("url") not in existing_urls]
    if new_articles:
        written = _append_articles(jsonl_path, new_articles)
        logger.info("English sources: wrote %d new articles", written)
    else:
        logger.info("English sources: no new articles found")
