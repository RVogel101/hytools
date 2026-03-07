"""RSS-based Armenian news scraper for English-language outlets.

Fetches and filters articles from Armenian media, diaspora publications,
and international outlets (keyword-filtered) via their public RSS/Atom
feeds.  Adapted from ``hyebot/app/scrapers/armenian_news.py``.

Supported sources (21 feeds):

**Armenia-based:**
  Armenpress, Asbarez, Armenian Weekly, Azatutyun (RFE/RL),
  Hetq, Panorama.am, EVN Report, OC Media, Civilnet

**Diaspora:**
  Massis Post, Armenian Mirror-Spectator, Horizon Weekly, Agos

**International (keyword-filtered):**
  Google News Armenia, Al Jazeera, Al-Monitor, BBC World,
  France 24, Deutsche Welle, Euronews

Output
------
Articles are written to a JSONL checkpoint file in
``<data_root>/raw/rss_news/articles.jsonl`` for downstream processing.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

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

_REQUEST_DELAY = 1.5  # seconds between requests


# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

_ARMENIAN_SOURCES: list[dict] = [
    # --- Armenia-based ---
    {"name": "Armenpress", "url": "https://armenpress.am/eng/news/", "rss": "https://armenpress.am/eng/rss/news/", "category": "news"},
    {"name": "Asbarez", "url": "https://asbarez.com", "rss": "https://asbarez.com/feed/", "category": "news"},
    {"name": "Armenian Weekly", "url": "https://armenianweekly.com", "rss": "https://armenianweekly.com/feed/", "category": "news"},
    {"name": "Azatutyun", "url": "https://www.azatutyun.am", "rss": "https://www.azatutyun.am/api/zijrreypui", "category": "news"},
    {"name": "Hetq", "url": "https://hetq.am/en/news", "rss": "https://hetq.am/en/rss", "category": "investigative"},
    {"name": "Panorama.am", "url": "https://www.panorama.am/en/news/", "rss": "https://www.panorama.am/en/rss/news.xml", "category": "news"},
    {"name": "EVN Report", "url": "https://evnreport.com", "rss": "https://evnreport.com/feed/", "category": "analysis"},
    {"name": "OC Media", "url": "https://oc-media.org", "rss": "https://oc-media.org/feed/", "category": "news"},
    {"name": "Civilnet", "url": "https://www.civilnet.am/en/", "rss": "https://www.civilnet.am/en/feed/", "category": "culture"},
    # --- Diaspora ---
    {"name": "Massis Post", "url": "https://massispost.com", "rss": "https://massispost.com/feed/", "category": "diaspora"},
    {"name": "Armenian Mirror-Spectator", "url": "https://mirrorspectator.com", "rss": "https://mirrorspectator.com/feed/", "category": "diaspora"},
    {"name": "Horizon Weekly", "url": "https://horizonweekly.ca", "rss": "https://horizonweekly.ca/feed/", "category": "diaspora"},
    {"name": "Agos", "url": "https://www.agos.com.tr/en", "rss": "https://www.agos.com.tr/en/rss", "category": "diaspora"},
]

_INTERNATIONAL_SOURCES: list[dict] = [
    {"name": "Google News - Armenia", "url": "https://news.google.com",
     "rss": "https://news.google.com/rss/search?q=Armenia+OR+Armenian+OR+Artsakh+OR+Karabakh&hl=en-US&gl=US&ceid=US:en",
     "category": "international", "keyword_filter": False, "google_news": True},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com", "rss": "https://www.aljazeera.com/xml/rss/all.xml", "category": "international", "keyword_filter": True},
    {"name": "Al-Monitor", "url": "https://www.al-monitor.com", "rss": "https://www.al-monitor.com/rss", "category": "international", "keyword_filter": True},
    {"name": "BBC World", "url": "https://www.bbc.co.uk/news/world", "rss": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "international", "keyword_filter": True},
    {"name": "France 24", "url": "https://www.france24.com/en/", "rss": "https://www.france24.com/en/rss", "category": "international", "keyword_filter": True},
    {"name": "Deutsche Welle", "url": "https://www.dw.com/en/", "rss": "https://rss.dw.com/xml/rss-en-world", "category": "international", "keyword_filter": True},
    {"name": "Euronews", "url": "https://www.euronews.com", "rss": "https://www.euronews.com/rss", "category": "international", "keyword_filter": True},
]

ALL_RSS_SOURCES = _ARMENIAN_SOURCES + _INTERNATIONAL_SOURCES


# ---------------------------------------------------------------------------
# Armenian keyword filter (for international feeds)
# ---------------------------------------------------------------------------

ARMENIAN_KEYWORDS: list[str] = [
    # Country / people / demonyms
    r"\barmenia\b", r"\barmenian[s]?\b", r"\bhay(?:astan)?\b",
    # Geography
    r"\byerevan\b", r"\bgyumri\b", r"\bvanadzor\b", r"\bsevan\b",
    r"\bararat\b", r"\bechmiadzin\b", r"\betchmiadzin\b",
    # Artsakh / Karabakh
    r"\bartsakh\b", r"\bkarabakh\b", r"\bnagorno[- ]?karabakh\b",
    r"\bstepanakert\b", r"\bshushi\b", r"\bshusha\b",
    # Genocide & historical events
    r"\barmenian[- ]?genocide\b", r"\bmedz\s*yeghern\b", r"\baghet\b",
    r"\bapril\s*24\b",
    # Political figures
    r"\bpash[iy]n[iy]an\b", r"\bkoch?ar[iy]an\b", r"\bsark?[iy]ss?[iy]an\b",
    # Conflict & diplomacy
    r"\bazerbaijan\b.*(?:armenia|ceasefire|border|peace|corridor)",
    r"\bturkey\b.*(?:armenia|border|protocol|normali[sz])",
    r"\bzangezur\s*corridor\b", r"\bminsk\s*group\b",
    r"\b44[- ]?day\s*war\b",
    # Diaspora & church
    r"\barmenian[- ]?diaspora\b", r"\barmenian[- ]?apostolic\b",
    r"\bduduk\b", r"\blavash\b", r"\bkhachkar\b",
    # Culture
    r"\baznavour\b", r"\btankian\b", r"\bsystem\s+of\s+a\s+down\b",
    r"\bkomitas\b", r"\bparajanov\b",
    # South Caucasus
    r"\bsouth[- ]?caucasus\b", r"\bcaucasus\b.*armenian",
]

_KEYWORD_PATTERN: re.Pattern[str] = re.compile(
    "|".join(ARMENIAN_KEYWORDS), re.IGNORECASE,
)


def _matches_armenian_keywords(text: str) -> bool:
    return bool(_KEYWORD_PATTERN.search(text))


# ---------------------------------------------------------------------------
# Google News source filtering
# ---------------------------------------------------------------------------

BLOCKED_SOURCES: set[str] = {
    # Russia
    "rt", "russia today", "rt.com", "sputnik", "sputniknews",
    "tass", "ria novosti", "ria news",
    # Azerbaijan
    "azernews", "azertag", "apa.az", "report.az", "caliber.az",
    "trend.az", "news.az", "day.az",
    # Turkey
    "trt", "trt world", "anadolu agency", "daily sabah",
}

# Sources we already scrape directly — filters duplicates from Google News
DUPLICATE_SOURCES: set[str] = {
    "armenpress", "asbarez", "the armenian weekly", "armenian weekly",
    "azatutyun", "radio free europe", "rfe/rl",
    "hetq", "hetq.am", "panorama.am",
    "evn report", "oc media", "civilnet",
    "massis post", "the armenian mirror-spectator",
    "mirror-spectator", "mirrorspectator",
    "horizon weekly", "agos",
    "euronews", "france 24", "al jazeera", "al-monitor",
    "bbc", "bbc world", "bbc news",
    "deutsche welle", "dw",
}

_BLOCKED_RE = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in BLOCKED_SOURCES) + r")\s*$",
    re.IGNORECASE,
)

_DUPLICATE_RE = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in DUPLICATE_SOURCES) + r")\s*$",
    re.IGNORECASE,
)


def _google_news_source_blocked(title: str) -> bool:
    """Google News titles end with '- Source Name'."""
    parts = title.rsplit(" - ", 1)
    if len(parts) < 2:
        return False
    return bool(_BLOCKED_RE.search(parts[-1].strip()))


def _google_news_source_duplicate(title: str) -> bool:
    parts = title.rsplit(" - ", 1)
    if len(parts) < 2:
        return False
    return bool(_DUPLICATE_RE.search(parts[-1].strip()))


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

def _parse_rss_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator=" ")


def _fetch_rss(rss_url: str, session: requests.Session) -> list[dict]:
    """Parse an RSS/Atom feed and return a list of entry dicts.

    Uses feedparser if available, otherwise falls back to XML parsing.
    """
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
            summary = _clean_text(_strip_html(raw_summary))[:1000]
            published = _parse_rss_date(
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
        return _fetch_rss_xml(rss_url, session)


def _fetch_rss_xml(rss_url: str, session: requests.Session) -> list[dict]:
    """Minimal RSS/Atom parser using stdlib xml.etree."""
    import xml.etree.ElementTree as ET
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

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        desc = _clean_text(_strip_html(item.findtext("description") or ""))[:1000]
        pub = _parse_rss_date(item.findtext("pubDate") or "")
        entries.append({
            "title": title,
            "url": url,
            "summary": desc,
            "published_at": pub.isoformat() if pub else None,
            "tags": [],
        })

    # Atom
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
        pub = _parse_rss_date(pub_str)
        entries.append({
            "title": title,
            "url": url,
            "summary": _clean_text(_strip_html(summary_el))[:1000],
            "published_at": pub.isoformat() if pub else None,
            "tags": [],
        })

    return entries


# ---------------------------------------------------------------------------
# Scrape logic
# ---------------------------------------------------------------------------

def _scrape_source(source: dict, session: requests.Session) -> list[dict]:
    """Scrape a single RSS source, applying filtering as configured."""
    name = source["name"]
    rss_url = source["rss"]
    logger.info("[%s] Fetching RSS feed: %s", name, rss_url)

    entries = _fetch_rss(rss_url, session)

    # Apply keyword filter for international sources
    if source.get("keyword_filter"):
        before = len(entries)
        entries = [
            e for e in entries
            if _matches_armenian_keywords(e["title"])
            or _matches_armenian_keywords(e.get("summary", ""))
        ]
        logger.info(
            "[%s] Keyword filter: %d/%d matched Armenian keywords",
            name, len(entries), before,
        )

    # Apply Google News source filtering
    if source.get("google_news"):
        before = len(entries)
        entries = [
            e for e in entries
            if not _google_news_source_blocked(e["title"])
            and not _google_news_source_duplicate(e["title"])
        ]
        logger.info(
            "[%s] Source filter: kept %d/%d (blocked/duplicate removed)",
            name, len(entries), before,
        )

    # Tag each entry with its source
    for e in entries:
        e["source_name"] = name
        e["source_url"] = source["url"]
        e["category"] = source.get("category", "news")

    logger.info("[%s] Collected %d articles", name, len(entries))
    return entries


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
    """Scrape all configured RSS news sources.

    Config keys used::

        paths:
          data_root: data       # base directory for output
        scraping:
          rss_news:
            enabled: true
            sources: null       # null = all sources; or list of names to include
            request_delay: 1.5
    """
    paths = config.get("paths", {})
    data_root = Path(paths.get("data_root", "data"))
    rss_cfg = config.get("scraping", {}).get("rss_news", {})

    request_delay = rss_cfg.get("request_delay", _REQUEST_DELAY)
    enabled_sources = rss_cfg.get("sources")  # None means all

    output_dir = data_root / "raw" / "rss_news"
    jsonl_path = output_dir / "articles.jsonl"
    existing_urls = _load_existing_urls(jsonl_path)

    session = requests.Session()
    session.headers.update(_HEADERS)

    total_new = 0
    for source in ALL_RSS_SOURCES:
        if enabled_sources and source["name"] not in enabled_sources:
            continue

        try:
            entries = _scrape_source(source, session)
        except Exception:
            logger.exception("[%s] Scrape failed", source["name"])
            continue

        # Deduplicate against existing checkpoint
        new_entries = [e for e in entries if e.get("url") not in existing_urls]
        if new_entries:
            written = _append_articles(jsonl_path, new_entries)
            existing_urls.update(e["url"] for e in new_entries)
            total_new += written
            logger.info("[%s] Wrote %d new articles", source["name"], written)

        time.sleep(request_delay)

    logger.info("RSS news scrape complete: %d new articles total", total_new)
