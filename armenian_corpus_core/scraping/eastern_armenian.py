"""Eastern Armenian corpus scraper (Republic of Armenia + diaspora Eastern variant sources).

Covers:
- Eastern Armenian Wikipedia (hy.wikipedia.org)
- Armenian news agencies (Armenpress, A1+, Armtimes, Aravot)
- Literary archives (Hayreniq, etc.)
- Historical collections

All sources tagged with Eastern dialect and appropriate region/date metadata.
"""

from __future__ import annotations

import json
import logging
import re
import time
import bz2
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Optional
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .metadata import TextMetadata, Dialect, Region, SourceType, ContentType

logger = logging.getLogger(__name__)

_DUMP_BASE = "https://dumps.wikimedia.org/{lang}wiki/{date}/"
_ARTICLES_DUMP = "{lang}wiki-{date}-pages-articles.xml.bz2"
_MW_NS = "http://www.mediawiki.org/xml/export-0.10/"

# Wikitext cleanup (same as Western Armenian scraper)
_RE_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")
_RE_FILE_LINK = re.compile(r"\[\[(File|Image|Պատկ):.*?\]\]", re.IGNORECASE)
_RE_CATEGORY = re.compile(r"\[\[Category:.*?\]\]", re.IGNORECASE)
_RE_EXT_LINK = re.compile(r"\[https?://[^\]]*\]")
_RE_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/]*/?>", re.DOTALL)
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_HEADING = re.compile(r"={2,6}\s*(.*?)\s*={2,6}")
_RE_BOLD_ITALIC = re.compile(r"'{2,5}")
_RE_LIST_MARKER = re.compile(r"^[*#:;]+\s*", re.MULTILINE)
_RE_TABLE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_RE_INTERNAL_LINK = re.compile(r"\[\[([^|\]]*\|)?([^\]]+)\]\]")
_RE_REDIRECT = re.compile(r"^#REDIRECT", re.IGNORECASE)
_RE_MULTI_WS = re.compile(r"\s+")

_MIN_ARMENIAN_CHARS = 30
_REQUEST_DELAY = 2.0
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
}

# News agency endpoints and fallback crawling rules.
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


def _clean_wikitext(raw: str) -> str:
    """Strip wikitext markup from raw and return plain text."""
    text = raw
    text = _RE_TEMPLATE.sub("", text)
    text = _RE_TABLE.sub("", text)
    text = _RE_FILE_LINK.sub("", text)
    text = _RE_CATEGORY.sub("", text)
    text = _RE_REF.sub("", text)
    text = _RE_HTML_TAG.sub("", text)
    text = _RE_EXT_LINK.sub("", text)
    text = _RE_HEADING.sub(r"\1", text)
    text = _RE_BOLD_ITALIC.sub("", text)
    text = _RE_LIST_MARKER.sub("", text)
    text = _RE_INTERNAL_LINK.sub(r"\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _resolve_dump_date(lang: str, requested: str) -> str:
    """Resolve dump date (handle 'latest')."""
    if requested != "latest":
        return requested
    url = _DUMP_BASE.format(lang=lang, date="latest") + "dumpstatus.json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("version", "latest")
    except Exception:
        logger.warning("Could not resolve latest dump date for %s; using 'latest'", lang)
        return "latest"


def _parse_datetime(value: Optional[str]) -> Optional[str]:
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


def _sanitize_filename(name: str, max_len: int = 180) -> str:
    """Create filesystem-safe filename from title text."""
    cleaned = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name)
    cleaned = _RE_MULTI_WS.sub(" ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_len]


def _armenian_char_count(text: str) -> int:
    """Count Armenian script characters in text."""
    return sum(1 for ch in text if "\u0530" <= ch <= "\u058F")


def _parse_rss_feed(feed_xml: str, base_url: str) -> list[dict[str, Optional[str]]]:
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
        items.append(
            {
                "title": (node.findtext("title") or "").strip() or None,
                "url": urljoin(base_url, raw_link),
                "published": _parse_datetime(node.findtext("pubDate")),
                "category": (node.findtext("category") or "").strip() or None,
            }
        )

    if items:
        return items

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
    }
    for entry in root.findall(".//atom:entry", ns):
        link_node = entry.find("atom:link", ns)
        href = link_node.attrib.get("href") if link_node is not None else ""
        href = (href or "").strip()
        if not href:
            continue
        items.append(
            {
                "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip() or None,
                "url": urljoin(base_url, href),
                "published": _parse_datetime(
                    entry.findtext("atom:updated", default="", namespaces=ns)
                    or entry.findtext("atom:published", default="", namespaces=ns)
                ),
                "category": None,
            }
        )

    return items


def _extract_readable_text(html: str) -> str:
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


def _fetch_feed_items(feed_url: str, timeout: int = 30) -> list[dict[str, Optional[str]]]:
    """Fetch and parse one RSS/Atom feed."""
    try:
        response = requests.get(feed_url, timeout=timeout, headers=_DEFAULT_HEADERS)
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

    return _parse_rss_feed(text, base_url=feed_url)


def _discover_feed_urls(base_url: str, timeout: int = 30) -> list[str]:
    """Discover RSS/Atom feed URLs from a site's homepage."""
    try:
        response = requests.get(base_url, timeout=timeout, headers=_DEFAULT_HEADERS)
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


def _extract_candidate_article_urls(
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


def _collect_fallback_article_urls(
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
            response = requests.get(seed, timeout=timeout, headers=_DEFAULT_HEADERS)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("%s fallback seed request failed %s: %s", agency_name, seed, exc)
            continue

        urls = _extract_candidate_article_urls(response.text, seed, patterns)
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            found.append(url)
            if len(found) >= target_count:
                break

    return found


def _extract_article_page_metadata(html: str) -> dict[str, Optional[str]]:
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
        "published": _parse_datetime(published_raw),
        "category": category,
    }


def _fetch_article_payload(url: str, timeout: int = 30) -> Optional[dict[str, Optional[str]]]:
    """Fetch article URL and return extracted text + metadata payload."""
    try:
        response = requests.get(url, timeout=timeout, headers=_DEFAULT_HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed article request %s: %s", url, exc)
        return None

    html = response.text
    text = _extract_readable_text(html)
    if len(text) < 250:
        return None
    if _armenian_char_count(text) < _MIN_ARMENIAN_CHARS:
        return None

    meta = _extract_article_page_metadata(html)
    return {
        "text": text,
        "title": meta.get("title"),
        "published": meta.get("published"),
        "category": meta.get("category"),
    }


def download_eastern_armenian_wikipedia(dump_date: str = "latest", dest_dir: Optional[Path] = None) -> Path:
    """Download Eastern Armenian Wikipedia dump (hy.wikipedia.org).

    Language code 'hy' is the official ISO 639-1 code for Eastern Armenian.
    Note: Western Armenian uses 'hyw', classical uses 'hye'.

    Args:
        dump_date: Date string (YYYYMMDD format) or 'latest'
        dest_dir: Download destination (defaults to data/raw/wikipedia_ea/)

    Returns:
        Path to the downloaded bz2 file
    """
    if dest_dir is None:
        dest_dir = Path("data/raw/wikipedia_ea")

    dest_dir.mkdir(parents=True, exist_ok=True)
    resolved_date = _resolve_dump_date("hy", dump_date)  # 'hy' = Eastern Armenian
    filename = _ARTICLES_DUMP.format(lang="hy", date=resolved_date)
    url = _DUMP_BASE.format(lang="hy", date=resolved_date) + filename
    dest = dest_dir / filename

    if dest.exists():
        logger.info("EA Wikipedia dump already downloaded: %s", dest)
        return dest

    logger.info("Downloading Eastern Armenian Wikipedia dump (hy) from %s", url)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    logger.info("Download complete: %s (%d bytes) [language_code=hy]", dest, dest.stat().st_size)
    return dest


def extract_eastern_armenian_wikipedia(
    dump_path: Path,
    output_dir: Path,
    metadata_jsonl: Optional[Path] = None,
) -> int:
    """Extract Eastern Armenian Wikipedia articles.

    Each article saved as .txt with accompanying .jsonl metadata entry.

    Args:
        dump_path: Path to hy-wiki XML dump
        output_dir: Directory to save .txt files
        metadata_jsonl: Optional path to write metadata JSONL (one entry per article)

    Returns:
        Number of articles extracted
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting EA Wikipedia articles from %s -> %s", dump_path, output_dir)

    count = 0
    extraction_date = datetime.now().isoformat()

    metadata_entries = []

    with bz2.open(dump_path, "rt", encoding="utf-8") as fh:
        context = ET.iterparse(fh, events=("end",))
        title = ""
        ns = ""
        for event, elem in context:
            tag = elem.tag.split("}", 1)[-1]

            if tag == "title":
                title = elem.text or ""
            elif tag == "ns":
                ns = elem.text or ""
            elif tag == "text" and ns == "0":
                raw = elem.text or ""
                if not raw or _RE_REDIRECT.match(raw):
                    elem.clear()
                    continue
                cleaned = _clean_wikitext(raw)
                if len(cleaned) < 50:
                    elem.clear()
                    continue

                # Save article
                safe_name = re.sub(r'[<>:"/\\|?*]', "_", title)[:200]
                out_path = output_dir / f"{safe_name}.txt"
                out_path.write_text(cleaned, encoding="utf-8")

                # Create metadata entry
                meta = TextMetadata.eastern_wikipedia(title, extraction_date)
                meta.source_url = f"https://hy.wikipedia.org/wiki/{title.replace(' ', '_')}"
                metadata_entries.append((out_path.name, meta.to_dict()))

                count += 1
                if count % 1000 == 0:
                    logger.info("  Extracted %d articles...", count)

                elem.clear()

    # Write metadata if requested
    if metadata_jsonl:
        metadata_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_jsonl, "w", encoding="utf-8") as fh:
            for filename, meta_dict in metadata_entries:
                fh.write(json.dumps({
                    "text_file": filename,
                    **meta_dict
                }, ensure_ascii=False) + "\n")
        logger.info("Wrote metadata for %d articles to %s", len(metadata_entries), metadata_jsonl)

    logger.info("Extraction complete: %d articles", count)
    return count


def scrape_news_agency(
    agency_name: str,
    output_dir: Path,
    max_articles: int = 500,
    save_metadata: bool = True,
) -> tuple[int, int]:
    """Scrape a single news agency for articles.

    Args:
        agency_name: Key in NEWS_AGENCIES dict (e.g., 'armenpress')
        output_dir: Directory to save articles
        max_articles: Maximum articles to scrape
        save_metadata: Whether to create metadata JSONL

    Returns:
        Tuple of (articles_scraped, articles_written)
    """
    if agency_name not in NEWS_AGENCIES:
        raise ValueError(f"Unknown news agency: {agency_name}")

    agency_config = NEWS_AGENCIES[agency_name]
    base_url = agency_config["url"]
    source_name = agency_config["source_name"]
    feed_urls = agency_config.get("rss_urls", [])

    output_dir.mkdir(parents=True, exist_ok=True)
    extraction_date = datetime.now().isoformat()

    logger.info("Scraping %s news agency from %s...", agency_name, base_url)

    scraped = 0
    written = 0
    metadata_entries = []
    seen_urls: set[str] = set()

    all_feed_urls = list(feed_urls)
    discovered_feeds = _discover_feed_urls(base_url)
    for discovered in discovered_feeds:
        if discovered not in all_feed_urls:
            all_feed_urls.append(discovered)

    for feed_url in all_feed_urls:
        items = _fetch_feed_items(feed_url)
        if not items:
            continue

        for item in items:
            if written >= max_articles:
                break

            article_url = item.get("url")
            if not article_url or article_url in seen_urls:
                continue

            seen_urls.add(article_url)
            scraped += 1

            payload = _fetch_article_payload(article_url)
            if not payload:
                continue

            article_text = payload["text"]
            raw_title = item.get("title") or payload.get("title") or f"{agency_name}_{scraped}"
            file_stem = _sanitize_filename(f"{scraped:06d}_{raw_title}")
            out_path = output_dir / f"{file_stem}.txt"
            out_path.write_text(article_text or "", encoding="utf-8")

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

            metadata_entries.append({"text_file": out_path.name, **meta.to_dict()})
            written += 1

            if written % 25 == 0:
                logger.info("%s: wrote %d/%d articles", agency_name, written, max_articles)

            time.sleep(_REQUEST_DELAY)

        if written >= max_articles:
            break

    # Fallback: crawl listing pages if feeds didn't yield enough
    if written < max_articles:
        remaining = max_articles - written
        fallback_urls = _collect_fallback_article_urls(agency_name, agency_config, target_count=remaining * 3)
        if fallback_urls:
            logger.info("%s: fallback discovered %d article URLs", agency_name, len(fallback_urls))

        for article_url in fallback_urls:
            if written >= max_articles:
                break
            if article_url in seen_urls:
                continue

            seen_urls.add(article_url)
            scraped += 1

            payload = _fetch_article_payload(article_url)
            if not payload:
                continue

            raw_title = payload.get("title") or f"{agency_name}_{scraped}"
            article_text = payload["text"]
            file_stem = _sanitize_filename(f"{scraped:06d}_{raw_title}")
            out_path = output_dir / f"{file_stem}.txt"
            out_path.write_text(article_text or "", encoding="utf-8")

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

            metadata_entries.append({"text_file": out_path.name, **meta.to_dict()})
            written += 1

            if written % 25 == 0:
                logger.info("%s: wrote %d/%d articles", agency_name, written, max_articles)

            time.sleep(_REQUEST_DELAY)

    if save_metadata:
        metadata_path = output_dir / f"{agency_name}_metadata.jsonl"
        with open(metadata_path, "w", encoding="utf-8") as fh:
            for entry in metadata_entries:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("%s: wrote metadata for %d articles to %s", agency_name, len(metadata_entries), metadata_path)

    return scraped, written


def scrape_all_news_agencies(
    output_dir: Path | None = None,
    max_articles_per_agency: int = 500,
) -> dict[str, tuple[int, int]]:
    """Scrape all configured news agencies.

    Args:
        output_dir: Base directory for output (defaults to data/raw/news_ea/)
        max_articles_per_agency: Max articles per agency

    Returns:
        Dict mapping agency name -> (scraped, written) counts
    """
    if output_dir is None:
        output_dir = Path("data/raw/news_ea")

    results = {}
    for agency_name in NEWS_AGENCIES:
        agency_dir = output_dir / agency_name
        try:
            scraped, written = scrape_news_agency(
                agency_name,
                agency_dir,
                max_articles=max_articles_per_agency,
            )
            results[agency_name] = (scraped, written)
            time.sleep(_REQUEST_DELAY)  # Polite delay between agencies
        except Exception as exc:
            logger.error("Error scraping %s: %s", agency_name, exc)
            results[agency_name] = (0, 0)

    return results


def run(config: dict | None = None) -> None:
    """Entry-point: scrape Eastern Armenian sources.

    Args:
        config: Configuration dict with 'paths' and 'scraping.eastern_armenian' keys.
            If None, only runs with default paths.
    """
    cfg = config or {}
    paths = cfg.get("paths", {})
    raw_dir = Path(paths.get("raw_dir", "data/raw"))
    ea_cfg = cfg.get("scraping", {}).get("eastern_armenian", {})

    do_wikipedia = ea_cfg.get("wikipedia", True)
    do_news = ea_cfg.get("news", True)
    max_articles = int(ea_cfg.get("max_articles_per_agency", 500))

    if do_wikipedia:
        logger.info("=== Downloading EA Wikipedia ===")
        dump_path = download_eastern_armenian_wikipedia(dest_dir=raw_dir / "wikipedia_ea")
        logger.info("=== Extracting EA Wikipedia ===")
        output_dir = raw_dir / "wikipedia_ea" / "extracted"
        metadata_path = raw_dir / "wikipedia_ea_metadata.jsonl"
        count = extract_eastern_armenian_wikipedia(dump_path, output_dir, metadata_path)
        logger.info("Extracted %d EA Wikipedia articles", count)

    if do_news:
        logger.info("=== Scraping EA News Agencies ===")
        results = scrape_all_news_agencies(raw_dir / "news_ea", max_articles_per_agency=max_articles)
        for agency, (scraped, written) in results.items():
            logger.info("%s: scraped=%d, written=%d", agency, scraped, written)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Eastern Armenian corpus")
    parser.add_argument("--wikipedia", action="store_true", help="Scrape EA Wikipedia")
    parser.add_argument("--news", action="store_true", help="Scrape news agencies")
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--output", type=Path, default=None, help="Output directory")
    parser.add_argument("--agency", default=None, help="Single news agency key to scrape")
    parser.add_argument("--max-articles", type=int, default=500, help="Max articles per agency")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if args.all or not (args.wikipedia or args.news):
        args.wikipedia = args.news = True

    if args.wikipedia:
        logger.info("=== Downloading EA Wikipedia ===")
        dump_path = download_eastern_armenian_wikipedia()
        logger.info("=== Extracting EA Wikipedia ===")
        output_dir = args.output / "wikipedia_ea" if args.output else Path("data/raw/wikipedia_ea")
        metadata_path = output_dir.parent / "wikipedia_ea_metadata.jsonl"
        count = extract_eastern_armenian_wikipedia(dump_path, output_dir, metadata_path)
        logger.info("Extracted %d EA Wikipedia articles", count)

    if args.news:
        logger.info("=== Scraping EA News Agencies ===")
        output_dir = args.output / "news_ea" if args.output else Path("data/raw/news_ea")
        if args.agency:
            agency_output_dir = output_dir / args.agency
            scraped, written = scrape_news_agency(
                args.agency,
                agency_output_dir,
                max_articles=args.max_articles,
            )
            logger.info("%s: scraped=%d, written=%d", args.agency, scraped, written)
        else:
            results = scrape_all_news_agencies(output_dir, max_articles_per_agency=args.max_articles)
            for agency, (scraped, written) in results.items():
                logger.info("%s: scraped=%d, written=%d", agency, scraped, written)
