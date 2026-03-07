"""Diaspora newspaper scraper for Western Armenian text.

Scrapes article text from Western Armenian diaspora newspapers using
Selenium (pages are JavaScript-rendered).

Supported sources:
- **Aztag Daily** (aztagdaily.com) — Beirut-based WA daily newspaper
- **Horizon Weekly** (horizonweekly.ca) — Montreal-based WA weekly
- **Asbarez** (asbarez.com) — California-based, mixed EA/WA

Articles are saved incrementally to a JSONL checkpoint file for resume
capability.
"""

from __future__ import annotations

import json
import logging
import re
import time
from hashlib import sha1
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag

import requests

logger = logging.getLogger(__name__)

_MIN_ARMENIAN_CHARS = 30
_REQUEST_DELAY = 2.0  # seconds between page loads


def _count_armenian_chars(text: str) -> int:
    return sum(1 for c in text if "\u0530" <= c <= "\u058F")


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


# ── Source definitions ───────────────────────────────────────────────────────

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
    base_url="https://horizonweekly.ca",
    listing_url_template="https://horizonweekly.ca/en/category/news/page/{page}",
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
    base_url="https://asbarez.com",
    listing_url_template="https://asbarez.com/category/armenia/page/{page}",
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

_ALL_SOURCES = {"aztag": AZTAG, "horizon": HORIZON, "asbarez": ASBAREZ}


def _extract_urls_from_html(
    html: str,
    source: NewspaperSource,
    seen: set[str],
) -> list[str]:
    """Extract candidate article links from raw HTML as a resilient fallback."""
    from bs4 import BeautifulSoup

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


def _load_checkpoint(checkpoint_path: Path) -> tuple[set[str], set[str]]:
    """Load already-scraped URLs and text hashes from the JSONL checkpoint file."""
    seen: set[str] = set()
    text_hashes: set[str] = set()
    if checkpoint_path.exists():
        with open(checkpoint_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                    seen.add(entry.get("url", ""))
                    digest = entry.get("text_sha1")
                    if isinstance(digest, str) and digest:
                        text_hashes.add(digest)
                except json.JSONDecodeError:
                    continue
    return seen, text_hashes


def _collect_article_urls(driver, source: NewspaperSource) -> list[str]:
    """Paginate through listing pages and collect unique article URLs."""
    from selenium.webdriver.common.by import By

    all_urls: list[str] = []
    seen: set[str] = set()

    for page_num in range(1, source.max_pages + 1):
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

        # Fallback 1: Parse current page HTML if selector extraction is empty.
        if found_on_page == 0:
            try:
                fallback_urls = _extract_urls_from_html(driver.page_source, source, seen)
                if fallback_urls:
                    all_urls.extend(fallback_urls)
                    found_on_page += len(fallback_urls)
            except Exception:
                pass

        # Fallback 2: Direct requests fetch to bypass client-side rendering differences.
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

    return "\n\n".join(paragraphs)


def scrape_source(
    source: NewspaperSource,
    output_dir: Path,
    max_articles: int = 0,
    min_armenian_chars: int = _MIN_ARMENIAN_CHARS,
    validate_wa: bool = False,
) -> int:
    """Scrape articles from a single newspaper source.

    Returns the number of new articles scraped.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"{source.name}_articles.jsonl"
    already_scraped, text_hashes = _load_checkpoint(checkpoint_path)

    is_western_armenian = None
    if validate_wa:
        try:
            from armenian_corpus_core.scraping._wa_filter import is_western_armenian as _is_wa
            is_western_armenian = _is_wa
        except ImportError:
            logger.warning("WA validator unavailable for %s", source.name)

    logger.info(
        "Scraping %s — %d articles already in checkpoint",
        source.name,
        len(already_scraped),
    )

    driver = _init_driver()
    new_count = 0
    try:
        urls = _collect_article_urls(driver, source)

        for url in urls:
            if url in already_scraped:
                continue
            if max_articles and new_count >= max_articles:
                break

            try:
                text = _extract_article_text(driver, url, source)
            except Exception as exc:
                logger.warning("Failed to extract %s: %s", url, exc)
                continue

            armenian_chars = _count_armenian_chars(text)
            if armenian_chars < min_armenian_chars:
                logger.debug("Skipping (too few Armenian chars): %s", url)
                continue

            if is_western_armenian is not None:
                try:
                    if not is_western_armenian(text[:5000]):
                        logger.debug("Skipping non-WA article: %s", url)
                        continue
                except Exception:
                    continue

            text_sha1 = sha1(text.encode("utf-8", errors="ignore")).hexdigest()
            if text_sha1 in text_hashes:
                logger.debug("Skipping duplicate text body: %s", url)
                continue
            text_hashes.add(text_sha1)

            entry = {
                "url": url,
                "source": source.name,
                "text": text,
                "chars": len(text),
                "armenian_chars": armenian_chars,
                "text_sha1": text_sha1,
            }
            with open(checkpoint_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

            new_count += 1
            if new_count % 50 == 0:
                logger.info("  Scraped %d new articles from %s…", new_count, source.name)

    finally:
        driver.quit()

    logger.info("Scraped %d new articles from %s", new_count, source.name)
    return new_count


def export_to_text(checkpoint_path: Path, output_dir: Path) -> int:
    """Export JSONL articles to individual .txt files for downstream processing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(checkpoint_path, encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            text = entry.get("text", "")
            if not text:
                continue
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", entry["url"].split("/")[-1])[:200]
            if not safe_name:
                safe_name = f"article_{count}"
            out_path = output_dir / f"{safe_name}.txt"
            out_path.write_text(text, encoding="utf-8")
            count += 1
    return count


def run(config: dict) -> None:
    """Entry-point: scrape all configured newspaper sources."""
    raw_dir = Path(config["paths"]["raw_dir"]) / "newspapers"
    news_cfg = config["scraping"].get("newspapers", {})
    sources_to_scrape: list[str] = news_cfg.get("sources", ["aztag", "horizon"])
    default_max_pages = int(news_cfg.get("max_pages", 100))
    default_max_articles = int(news_cfg.get("max_articles_per_source", 0))
    min_armenian_chars = int(news_cfg.get("min_armenian_chars", _MIN_ARMENIAN_CHARS))
    validate_wa = bool(news_cfg.get("validate_wa", True))
    source_overrides = news_cfg.get("source_overrides", {})

    for source_name in sources_to_scrape:
        source = _ALL_SOURCES.get(source_name)
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

        source_dir = raw_dir / source_name
        scrape_source(
            runtime_source,
            source_dir,
            max_articles=int(override_cfg.get("max_articles", default_max_articles)),
            min_armenian_chars=min_armenian_chars,
            validate_wa=validate_wa,
        )
        checkpoint = source_dir / f"{source_name}_articles.jsonl"
        if checkpoint.exists():
            export_to_text(checkpoint, source_dir / "text")
