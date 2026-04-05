"""Western Armenian web discovery crawler.

Implements the phased crawler plan with:
- static seed loading
- optional DuckDuckGo search seeding
- respectful BFS crawling with robots.txt and per-domain rate limiting
- safe HTML-only fetching with SSRF guards and response-size caps
- Armenian ratio + dialect classification using the existing classifier
- MongoDB ingestion via ScrapedDocument / insert_or_skip
- incremental crawl state persisted in MongoDB when available
- optional Playwright fallback for JavaScript-rendered sites
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import logging
import re
import socket
import time
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
import yaml
from bs4 import BeautifulSoup

from hytools.ingestion._shared.helpers import insert_or_skip, open_mongodb_client
from hytools.ingestion._shared.review_queue import (
    PRIORITY_BORDERLINE_CRAWLER,
    ReviewItem,
    build_review_run_id,
    enqueue_for_review,
    get_review_collection,
    should_enqueue_low_confidence_classification,
)
from hytools.ingestion._shared.scraped_document import ScrapedDocument
from hytools.linguistics.dialect.branch_dialect_classifier import (
    classify_text_classification,
    get_wa_score_threshold,
)
from hytools.linguistics.dialect.review_audit import get_stage_review_settings

from .news import RSS_BLOCKED_SOURCES
from .search_seeder import DuckDuckGoSearchSeeder, load_existing_corpus_seed_urls
from .wa_crawler_audit import build_audit_rows, write_audit_reports

logger = logging.getLogger(__name__)
_STAGE = "web_crawler"

DEFAULT_USER_AGENT = "HytoolsCorpusCrawler/1.0 (+https://github.com/RVogel101/hytools)"
DEFAULT_SEED_FILE = Path("data/retrieval/crawler_seeds.txt")
DEFAULT_DISCOVERY_REPORT = Path("data/retrieval/crawler_found.csv")
DEFAULT_AUDIT_CSV = Path("data/retrieval/wa_crawler_audit.csv")
DEFAULT_AUDIT_JSON = Path("data/retrieval/wa_crawler_audit.json")
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
TRACKING_QUERY_KEYS = frozenset({
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_source",
    "utm_term",
})


@dataclass
class CrawlResult:
    """Single page crawl result."""

    url: str
    domain: str
    depth: int
    status_code: int
    text: str
    title: str
    armenian_char_ratio: float
    wa_score: float
    links_found: list[str] = field(default_factory=list)
    fetch_time_ms: int = 0
    robots_allowed: bool = True
    dialect_label: str = "inconclusive"
    dialect_confidence: float = 0.0
    western_score: float = 0.0
    eastern_score: float = 0.0
    classical_score: float = 0.0
    source_language_code: str = "hy"
    internal_language_code: str = "hy"
    internal_language_branch: str | None = None
    dialect: str = "unknown"
    original_url: str | None = None


@dataclass
class DomainProfile:
    """Aggregated stats for a crawled domain."""

    domain: str
    pages_crawled: int = 0
    pages_accepted: int = 0
    mean_wa_score: float = 0.0
    total_chars: int = 0
    first_seen_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_crawled_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sample_urls: list[str] = field(default_factory=list)

    def add_page(self, *, accepted: bool, wa_score: float, text: str, url: str) -> None:
        self.pages_crawled += 1
        self.last_crawled_iso = datetime.now(timezone.utc).isoformat()
        if not accepted:
            return

        running_total = self.mean_wa_score * self.pages_accepted
        self.pages_accepted += 1
        self.mean_wa_score = round((running_total + wa_score) / self.pages_accepted, 4)
        self.total_chars += len((text or "").strip())
        if url and url not in self.sample_urls and len(self.sample_urls) < 5:
            self.sample_urls.append(url)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "kind": "domain_profile",
            "domain": self.domain,
            "pages_crawled": self.pages_crawled,
            "pages_accepted": self.pages_accepted,
            "mean_wa_score": self.mean_wa_score,
            "total_chars": self.total_chars,
            "first_seen_iso": self.first_seen_iso,
            "last_crawled_iso": self.last_crawled_iso,
            "sample_urls": list(self.sample_urls),
        }


def _stage_config(config: dict | None) -> dict[str, Any]:
    if not config:
        return {}

    if "scraping" not in config and "ingestion" not in config:
        return dict(config)

    merged: dict[str, Any] = {}
    for top_level in ("scraping", "ingestion"):
        section = (config or {}).get(top_level) or {}
        stage = section.get("web_crawler")
        if isinstance(stage, dict):
            merged.update(stage)
    return merged


def _canonical_domain(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower().strip(".")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _root_domain_allowed(domain: str, allowed_domains: set[str]) -> bool:
    if not domain:
        return False
    if domain in allowed_domains:
        return True
    return any(domain.endswith(f".{allowed}") for allowed in allowed_domains)


class WAWebCrawler:
    """BFS web crawler with Armenian filtering and dialect scoring."""

    def __init__(
        self,
        config: dict,
        *,
        client=None,
        seed_file: Path | None = None,
        max_depth: int | None = None,
        max_pages_per_domain: int | None = None,
        request_delay: float | None = None,
        wa_threshold: float | None = None,
        user_agent: str | None = None,
    ):
        stage_cfg = _stage_config(config)
        self.config = config or {}
        self.stage_cfg = stage_cfg
        self.client = client

        self.seed_file = Path(seed_file or stage_cfg.get("seed_file") or DEFAULT_SEED_FILE)
        self.max_depth = int(max_depth if max_depth is not None else stage_cfg.get("max_depth", 2))
        self.max_pages_per_domain = int(
            max_pages_per_domain if max_pages_per_domain is not None else stage_cfg.get("max_pages_per_domain", 50)
        )
        self.max_total_pages = int(stage_cfg.get("max_total_pages", 500))
        self.request_delay = float(request_delay if request_delay is not None else stage_cfg.get("request_delay_seconds", 2.0))
        self.wa_threshold = float(wa_threshold if wa_threshold is not None else stage_cfg.get("wa_threshold", get_wa_score_threshold()))
        self.min_armenian_ratio = float(stage_cfg.get("min_armenian_ratio", 0.10))
        self.min_text_chars = int(stage_cfg.get("min_text_chars", 200))
        self.user_agent = str(user_agent or stage_cfg.get("user_agent") or DEFAULT_USER_AGENT)
        self.max_response_bytes = int(stage_cfg.get("max_response_bytes", 5 * 1024 * 1024))
        self.max_robots_bytes = int(stage_cfg.get("max_robots_bytes", 512 * 1024))
        self.allow_http = bool(stage_cfg.get("allow_http", False))
        self.allow_external_domains = bool(stage_cfg.get("allow_external_domains", False))
        self.state_collection_name = str(stage_cfg.get("state_collection", "crawler_state"))
        self.discovery_report_path = Path(stage_cfg.get("discovery_report", DEFAULT_DISCOVERY_REPORT))
        self.audit_csv_path = Path(stage_cfg.get("audit_report_csv", DEFAULT_AUDIT_CSV))
        self.audit_json_path = Path(stage_cfg.get("audit_report_json", DEFAULT_AUDIT_JSON))
        review_overrides = stage_cfg.get("review_queue") if isinstance(stage_cfg.get("review_queue"), dict) else {}
        review_cfg = get_stage_review_settings("web_crawler", review_overrides)
        self.review_queue_enabled = bool(review_cfg.get("enabled", True))
        self.review_queue_source = str(review_cfg.get("queue_source", "crawler") or "crawler")
        self.review_confidence_threshold = float(review_cfg.get("confidence_threshold", 0.35))
        self.review_score_margin_threshold = float(review_cfg.get("score_margin_threshold", 2.0))
        self.review_min_armenian_ratio = float(
            review_cfg.get("min_armenian_ratio", max(self.min_armenian_ratio * 0.75, 0.05))
        )

        incremental_cfg = stage_cfg.get("incremental") if isinstance(stage_cfg.get("incremental"), dict) else {}
        self.incremental_enabled = bool(incremental_cfg.get("enabled", True))
        self.recrawl_after_hours = float(incremental_cfg.get("recrawl_after_hours", 24.0 * 7.0))
        self.resume_frontier = bool(incremental_cfg.get("resume_frontier", True))
        self.state_sync_every = max(1, int(incremental_cfg.get("state_sync_every", 25)))

        playwright_cfg = stage_cfg.get("playwright_fallback") if isinstance(stage_cfg.get("playwright_fallback"), dict) else {}
        self.playwright_enabled = bool(playwright_cfg.get("enabled", False))
        self.playwright_timeout_ms = int(playwright_cfg.get("timeout_ms", 15_000))

        search_cfg = stage_cfg.get("search_seeding") if isinstance(stage_cfg.get("search_seeding"), dict) else {}
        self.search_enabled = bool(search_cfg.get("enabled", False))
        blocked_domains = {_canonical_domain(f"https://{name}") for name in RSS_BLOCKED_SOURCES}
        self.search_seeder = DuckDuckGoSearchSeeder(
            queries=search_cfg.get("queries"),
            max_results_per_query=int(search_cfg.get("max_results_per_query", 10)),
            blocked_domains=blocked_domains,
        )
        self.search_include_corpus_urls = bool(search_cfg.get("include_existing_corpus_urls", True))
        self.search_existing_corpus_seed_limit = int(search_cfg.get("existing_corpus_seed_limit", 250))

        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "hy,en-US;q=0.8,en;q=0.6",
            }
        )
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._last_request_started: dict[str, float] = {}
        self._pages_per_domain: Counter[str] = Counter()
        self._profiles: dict[str, DomainProfile] = {}
        self._accepted_results: list[CrawlResult] = []
        self._allowed_domains: set[str] = set()
        self._seen_urls: set[str] = set()
        self._run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        self._ensure_state_indexes()

    @property
    def state_collection(self):
        if self.client is None:
            return None
        try:
            return self.client.db[self.state_collection_name]
        except Exception:
            logger.debug("Web crawler: crawler_state collection unavailable", exc_info=True)
            return None

    @property
    def review_collection(self):
        if not self.review_queue_enabled:
            return None
        return get_review_collection(self.client)

    def _ensure_state_indexes(self) -> None:
        collection = self.state_collection
        if collection is None:
            return
        try:
            collection.create_index([("kind", 1), ("domain", 1)], sparse=True)
            collection.create_index([("kind", 1), ("updated_at", -1)])
            collection.create_index([("kind", 1), ("last_crawled_iso", -1)])
        except Exception:
            logger.debug("Web crawler: state index creation failed", exc_info=True)

    def _should_enqueue_borderline_review(self, result: CrawlResult, accepted: bool) -> bool:
        if accepted or not self.review_queue_enabled or not (result.text or "").strip():
            return False

        classification = {
            "label": result.dialect_label,
            "confidence": result.dialect_confidence,
            "western_score": result.western_score,
            "eastern_score": result.eastern_score,
            "classical_score": result.classical_score,
        }
        near_ratio_threshold = result.armenian_char_ratio >= self.review_min_armenian_ratio
        near_wa_threshold = result.wa_score >= max(self.wa_threshold * 0.5, 1.0)
        return (
            should_enqueue_low_confidence_classification(
                classification,
                confidence_threshold=self.review_confidence_threshold,
                score_margin_threshold=self.review_score_margin_threshold,
            )
            or near_ratio_threshold
            or near_wa_threshold
        )

    def _enqueue_borderline_review(self, result: CrawlResult) -> None:
        collection = self.review_collection
        if collection is None:
            return

        detail = (
            f"ratio={result.armenian_char_ratio:.3f} min_ratio={self.min_armenian_ratio:.3f} "
            f"wa_score={result.wa_score:.3f} wa_threshold={self.wa_threshold:.3f} "
            f"label={result.dialect_label} confidence={result.dialect_confidence:.3f}"
        )
        enqueue_for_review(
            collection,
            ReviewItem(
                run_id=build_review_run_id(self.review_queue_source, _STAGE, result.url, "borderline_crawl_page"),
                pdf_path=result.url,
                pdf_name=result.title or result.domain,
                page_num=0,
                reason="borderline_crawl_page",
                priority=PRIORITY_BORDERLINE_CRAWLER,
                detail=detail,
                queue_source=self.review_queue_source,
                stage=_STAGE,
                item_id=result.url,
                title=result.title,
                source_url=result.url,
                extra={
                    "domain": result.domain,
                    "depth": result.depth,
                    "armenian_char_ratio": round(result.armenian_char_ratio, 4),
                    "wa_score": round(result.wa_score, 4),
                    "dialect_label": result.dialect_label,
                    "dialect_confidence": round(result.dialect_confidence, 4),
                },
            ),
        )

    def load_seeds(self) -> list[str]:
        seeds: list[str] = []
        if not self.seed_file.exists():
            logger.warning("Web crawler seed file missing: %s", self.seed_file)
            return seeds

        for line in self.seed_file.read_text(encoding="utf-8").splitlines():
            candidate = line.strip()
            if not candidate or candidate.startswith("#"):
                continue
            normalized = self.normalize_url(candidate)
            if normalized:
                seeds.append(normalized)
        return seeds

    def normalize_url(self, url: str, *, base_url: str | None = None) -> str | None:
        if not url:
            return None
        joined = urljoin(base_url or "", url.strip()) if base_url else url.strip()
        joined, _ = urldefrag(joined)
        parsed = urlparse(joined)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        if not self.allow_http and parsed.scheme != "https":
            return None

        query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in TRACKING_QUERY_KEYS]
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=parsed.path or "/",
            query=urlencode(query_pairs, doseq=True),
        )
        return urlunparse(normalized).rstrip("/") if normalized.path != "/" else urlunparse(normalized)

    def _is_safe_url(self, url: str) -> bool:
        hostname = urlparse(url).hostname
        if not hostname:
            return False
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False

        for info in infos:
            try:
                addr = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
                logger.warning("Web crawler blocked unsafe address %s -> %s", url, addr)
                return False
        return True

    def _is_html_response(self, response: requests.Response) -> bool:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        return content_type in ALLOWED_CONTENT_TYPES

    def _respect_rate_limit(self, domain: str) -> None:
        now = time.monotonic()
        last_started = self._last_request_started.get(domain)
        if last_started is not None:
            delay_remaining = self.request_delay - (now - last_started)
            if delay_remaining > 0:
                time.sleep(delay_remaining)
        self._last_request_started[domain] = time.monotonic()

    def _get_robots_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain in self._robots_cache:
            return self._robots_cache[domain]

        parser = RobotFileParser()
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser.set_url(robots_url)

        try:
            response = self._session.get(robots_url, timeout=(5, 5), stream=True)
            body = self._read_response_bytes(response, max_bytes=self.max_robots_bytes)
            if response.ok and body is not None:
                parser.parse(body.decode(response.encoding or "utf-8", errors="replace").splitlines())
            else:
                parser.parse([])
        except Exception:
            parser.parse([])
        self._robots_cache[domain] = parser
        return parser

    def check_robots(self, url: str) -> bool:
        parser = self._get_robots_parser(url)
        try:
            return bool(parser.can_fetch(self.user_agent, url))
        except Exception:
            return True

    def _read_response_bytes(self, response: requests.Response, *, max_bytes: int) -> bytes | None:
        content = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > max_bytes:
                    logger.warning("Web crawler response exceeded size cap: %s", response.url)
                    response.close()
                    return None
        except Exception:
            return None
        return bytes(content)

    def _fetch_via_requests(self, url: str) -> tuple[str, str, int, int] | None:
        if not self._is_safe_url(url):
            return None

        domain = _canonical_domain(url)
        self._respect_rate_limit(domain)
        started = time.monotonic()
        response: requests.Response | None = None
        try:
            response = self._session.get(url, timeout=(5, 30), stream=True, allow_redirects=True)
            final_url = self.normalize_url(response.url or url)
            if response.status_code >= 400 or not final_url:
                return None
            if not self.allow_http and urlparse(final_url).scheme != "https":
                return None
            final_domain = _canonical_domain(final_url)
            if not self.allow_external_domains and self._allowed_domains and not _root_domain_allowed(final_domain, self._allowed_domains):
                logger.warning("Web crawler blocked redirect outside allowed domains: %s -> %s", url, final_url)
                return None
            if not self._is_safe_url(final_url):
                return None
            if not self._is_html_response(response):
                return None
            payload = self._read_response_bytes(response, max_bytes=self.max_response_bytes)
            if payload is None:
                return None
            html = payload.decode(response.encoding or "utf-8", errors="replace")
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return html, final_url, int(response.status_code), elapsed_ms
        except requests.RequestException as exc:
            logger.debug("Web crawler request failed for %s: %s", url, exc)
            return None
        finally:
            if response is not None:
                response.close()

    def _fetch_via_playwright(self, url: str) -> tuple[str, str, int, int] | None:
        if not self.playwright_enabled:
            return None
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright fallback requested but playwright is not installed")
            return None

        started = time.monotonic()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.user_agent)
                page.goto(url, wait_until="networkidle", timeout=self.playwright_timeout_ms)
                final_url = self.normalize_url(page.url or url)
                html = page.content()
                browser.close()
        except Exception as exc:
            logger.debug("Playwright fallback failed for %s: %s", url, exc)
            return None

        if not final_url:
            return None
        final_domain = _canonical_domain(final_url)
        if not self.allow_external_domains and self._allowed_domains and not _root_domain_allowed(final_domain, self._allowed_domains):
            return None
        if not self._is_safe_url(final_url):
            return None
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return html, final_url, 200, elapsed_ms

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for tag in soup.find_all("a", href=True):
            normalized = self.normalize_url(tag.get("href", ""), base_url=base_url)
            if not normalized:
                continue
            domain = _canonical_domain(normalized)
            if not self.allow_external_domains and self._allowed_domains and not _root_domain_allowed(domain, self._allowed_domains):
                continue
            if normalized not in seen:
                seen.add(normalized)
                links.append(normalized)
        return links

    def _extract_text(self, soup: BeautifulSoup) -> str:
        for tag in soup.find_all(["script", "style", "noscript", "iframe", "object", "embed", "nav", "header", "footer", "aside"]):
            tag.decompose()
        for tag in soup.select(
            "[role=navigation], .cookie-banner, .social-share, .share-buttons, .sidebar, .widget, .ad, .advertisement"
        ):
            tag.decompose()

        parts: list[str] = []
        for tag in soup.find_all(["p", "li", "blockquote", "h1", "h2", "h3", "h4"]):
            text = tag.get_text(" ", strip=True)
            if len(text) >= 15:
                parts.append(text)
        body = "\n\n".join(parts).strip()
        if len(body) >= self.min_text_chars:
            return unicodedata.normalize("NFC", body)

        full = soup.get_text("\n", strip=True)
        full = re.sub(r"\n{3,}", "\n\n", full).strip()
        return unicodedata.normalize("NFC", full)

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        for selector in ("h1", "title"):
            node = soup.select_one(selector)
            if node:
                text = node.get_text(" ", strip=True)
                if text:
                    return text
        return url

    def _armenian_char_ratio(self, text: str) -> float:
        stripped = (text or "").strip()
        if not stripped:
            return 0.0
        arm_chars = sum(1 for char in stripped if "\u0531" <= char <= "\u058F")
        return round(arm_chars / max(len(stripped), 1), 4)

    def _classify_text_meta(self, text: str) -> dict[str, Any]:
        ratio = self._armenian_char_ratio(text)
        meta: dict[str, Any] = {
            "accepted": bool(ratio >= self.min_armenian_ratio and len((text or "").strip()) >= self.min_text_chars),
            "armenian_char_ratio": ratio,
            "dialect_label": "inconclusive",
            "dialect_confidence": 0.0,
            "western_score": 0.0,
            "eastern_score": 0.0,
            "classical_score": 0.0,
            "wa_score": 0.0,
            "source_language_code": "hy",
            "internal_language_code": "hy",
            "internal_language_branch": None,
            "dialect": "unknown",
        }
        if not meta["accepted"]:
            return meta

        result = classify_text_classification((text or "")[:12000])
        label = result.get("label", "inconclusive")
        western_score = float(result.get("western_score", 0.0) or 0.0)
        eastern_score = float(result.get("eastern_score", 0.0) or 0.0)
        classical_score = float(result.get("classical_score", 0.0) or 0.0)

        meta.update(
            {
                "dialect_label": label,
                "dialect_confidence": float(result.get("confidence", 0.0) or 0.0),
                "western_score": western_score,
                "eastern_score": eastern_score,
                "classical_score": classical_score,
                "wa_score": western_score,
            }
        )

        if label == "likely_western" or (western_score >= self.wa_threshold and western_score > eastern_score):
            meta.update(
                {
                    "source_language_code": "hyw",
                    "internal_language_branch": "hye-w",
                    "dialect": "western_armenian",
                }
            )
        elif label == "likely_eastern" or (eastern_score >= self.wa_threshold and eastern_score > western_score):
            meta.update(
                {
                    "source_language_code": "hye",
                    "internal_language_branch": "hye-e",
                    "dialect": "eastern_armenian",
                }
            )
        elif label == "likely_classical" or classical_score >= self.wa_threshold:
            meta.update(
                {
                    "source_language_code": "xcl",
                    "dialect": "classical_armenian",
                }
            )

        return meta

    def classify_page(self, text: str) -> dict[str, Any] | None:
        meta = self._classify_text_meta(text)
        if not meta["accepted"]:
            return None
        return meta

    def score_page(self, text: str) -> tuple[float, float]:
        meta = self._classify_text_meta(text)
        return meta["armenian_char_ratio"], meta["wa_score"]

    def fetch_page(self, url: str, depth: int = 0) -> CrawlResult | None:
        normalized = self.normalize_url(url)
        if not normalized:
            return None
        if not self.check_robots(normalized):
            logger.info("Web crawler robots.txt denied %s", normalized)
            return None

        payload = self._fetch_via_requests(normalized)
        if payload is None:
            return None

        html, final_url, status_code, fetch_time_ms = payload
        soup = BeautifulSoup(html, "lxml")
        links_found = self._extract_links(soup, final_url)
        title = self._extract_title(soup, final_url)
        text = self._extract_text(soup)

        if self.playwright_enabled and len(text) < self.min_text_chars:
            playwright_payload = self._fetch_via_playwright(final_url)
            if playwright_payload is not None:
                html, final_url, status_code, fetch_time_ms = playwright_payload
                soup = BeautifulSoup(html, "lxml")
                links_found = self._extract_links(soup, final_url)
                title = self._extract_title(soup, final_url)
                text = self._extract_text(soup)

        meta = self._classify_text_meta(text)
        return CrawlResult(
            url=final_url,
            original_url=normalized,
            domain=_canonical_domain(final_url),
            depth=depth,
            status_code=status_code,
            text=text,
            title=title,
            armenian_char_ratio=float(meta["armenian_char_ratio"]),
            wa_score=float(meta["wa_score"]),
            links_found=links_found,
            fetch_time_ms=fetch_time_ms,
            robots_allowed=True,
            dialect_label=str(meta["dialect_label"]),
            dialect_confidence=float(meta["dialect_confidence"]),
            western_score=float(meta["western_score"]),
            eastern_score=float(meta["eastern_score"]),
            classical_score=float(meta["classical_score"]),
            source_language_code=str(meta["source_language_code"]),
            internal_language_code=str(meta["internal_language_code"]),
            internal_language_branch=meta["internal_language_branch"],
            dialect=str(meta["dialect"]),
        )

    def _seed_domains(self, seeds: Iterable[str]) -> None:
        for seed in seeds:
            domain = _canonical_domain(seed)
            if domain:
                self._allowed_domains.add(domain)

    def _filter_recent_seed_urls(self, seeds: Sequence[str]) -> list[str]:
        if not self.incremental_enabled or self.state_collection is None:
            return list(seeds)

        domains = {_canonical_domain(seed) for seed in seeds if seed}
        if not domains:
            return list(seeds)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recrawl_after_hours)
        recent_domains: set[str] = set()
        try:
            cursor = self.state_collection.find(
                {"kind": "domain_profile", "domain": {"$in": sorted(domains)}},
                {"domain": 1, "last_crawled_iso": 1},
            )
            for doc in cursor:
                last_crawled = doc.get("last_crawled_iso")
                if not last_crawled:
                    continue
                try:
                    if datetime.fromisoformat(last_crawled) >= cutoff:
                        recent_domains.add(doc.get("domain", ""))
                except ValueError:
                    continue
        except Exception as exc:
            logger.warning("Web crawler could not read incremental state: %s", exc)
            return list(seeds)

        return [seed for seed in seeds if _canonical_domain(seed) not in recent_domains]

    def _load_existing_crawled_urls(self) -> set[str]:
        if self.client is None or not self.incremental_enabled or not self._allowed_domains:
            return set()
        seen: set[str] = set()
        try:
            cursor = self.client.documents.find(
                {"source": "web_crawler", "metadata.domain": {"$in": sorted(self._allowed_domains)}},
                {"metadata.url": 1},
            )
            for doc in cursor:
                url = ((doc or {}).get("metadata") or {}).get("url")
                normalized = self.normalize_url(url)
                if normalized:
                    seen.add(normalized)
        except Exception as exc:
            logger.warning("Web crawler could not load previously crawled URLs: %s", exc)
        return seen

    def _load_frontier_checkpoint(self) -> deque[tuple[str, int]]:
        if not self.incremental_enabled or not self.resume_frontier or self.state_collection is None:
            return deque()
        try:
            doc = self.state_collection.find_one({"_id": "frontier_checkpoint"}) or {}
        except Exception:
            logger.debug("Web crawler frontier checkpoint load failed", exc_info=True)
            return deque()
        pending = doc.get("pending") or []
        checkpoint = deque()
        for item in pending:
            url = self.normalize_url((item or {}).get("url", ""))
            depth = int((item or {}).get("depth", 0))
            if url:
                checkpoint.append((url, depth))
        return checkpoint

    def _save_frontier_checkpoint(self, frontier: deque[tuple[str, int]]) -> None:
        if not self.incremental_enabled or self.state_collection is None:
            return
        pending = [{"url": url, "depth": depth} for url, depth in list(frontier)]
        try:
            self.state_collection.update_one(
                {"_id": "frontier_checkpoint"},
                {
                    "$set": {
                        "kind": "frontier_checkpoint",
                        "pending": pending,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "run_id": self._run_id,
                    }
                },
                upsert=True,
            )
        except Exception:
            logger.debug("Web crawler frontier checkpoint save failed", exc_info=True)

    def _clear_frontier_checkpoint(self) -> None:
        if self.state_collection is None:
            return
        try:
            self.state_collection.delete_one({"_id": "frontier_checkpoint"})
        except Exception:
            logger.debug("Web crawler frontier checkpoint clear failed", exc_info=True)

    def _persist_domain_profile(self, profile: DomainProfile) -> None:
        if self.state_collection is None:
            return
        try:
            self.state_collection.update_one(
                {"kind": "domain_profile", "domain": profile.domain},
                {
                    "$set": {
                        **profile.to_state_dict(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "run_id": self._run_id,
                    }
                },
                upsert=True,
            )
        except Exception:
            logger.debug("Web crawler domain profile save failed", exc_info=True)

    def _persist_run_summary(self, *, profiles: Sequence[DomainProfile], frontier_remaining: int) -> None:
        if self.state_collection is None:
            return
        try:
            self.state_collection.update_one(
                {"_id": f"run_summary:{self._run_id}"},
                {
                    "$set": {
                        "kind": "run_summary",
                        "run_id": self._run_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "frontier_remaining": frontier_remaining,
                        "domains": len(profiles),
                        "pages_crawled": sum(profile.pages_crawled for profile in profiles),
                        "pages_accepted": sum(profile.pages_accepted for profile in profiles),
                    }
                },
                upsert=True,
            )
        except Exception:
            logger.debug("Web crawler run summary save failed", exc_info=True)

    def _profile_for_domain(self, domain: str) -> DomainProfile:
        if domain not in self._profiles:
            self._profiles[domain] = DomainProfile(domain=domain)
        return self._profiles[domain]

    def _should_accept_result(self, result: CrawlResult) -> bool:
        return bool(result.text and len(result.text.strip()) >= self.min_text_chars and result.armenian_char_ratio >= self.min_armenian_ratio)

    def _insert_result(self, result: CrawlResult) -> None:
        if self.client is None:
            return

        metadata = {
            "source_language_codes": [result.source_language_code],
            "domain": result.domain,
            "crawl_depth": result.depth,
            "crawler_version": "1.0",
            "status_code": result.status_code,
            "robots_allowed": result.robots_allowed,
            "fetch_time_ms": result.fetch_time_ms,
            "armenian_char_ratio": round(result.armenian_char_ratio, 4),
            "original_url": result.original_url,
        }
        scraped = ScrapedDocument(
            source_family="web_crawler",
            text=result.text,
            title=result.title,
            source_url=result.url,
            source_name=result.domain,
            source_language_code=result.source_language_code,
            internal_language_code=result.internal_language_code,
            internal_language_branch=result.internal_language_branch,
            wa_score=round(result.wa_score, 4),
            source_type="website",
            content_type="article",
            writing_category="article",
            dialect=result.dialect,
            dialect_label=result.dialect_label,
            dialect_confidence=result.dialect_confidence,
            western_score=round(result.western_score, 4),
            eastern_score=round(result.eastern_score, 4),
            classical_score=round(result.classical_score, 4),
            extra=metadata,
        )
        insert_or_skip(self.client, doc=scraped, config=self.config)

    def _write_discovery_report(self, profiles: Sequence[DomainProfile]) -> None:
        self.discovery_report_path.parent.mkdir(parents=True, exist_ok=True)
        with self.discovery_report_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "domain",
                    "pages_crawled",
                    "pages_accepted",
                    "mean_wa_score",
                    "total_chars",
                    "first_seen_iso",
                    "last_crawled_iso",
                    "sample_url",
                ],
            )
            writer.writeheader()
            for profile in sorted(profiles, key=lambda item: item.domain):
                writer.writerow(
                    {
                        "domain": profile.domain,
                        "pages_crawled": profile.pages_crawled,
                        "pages_accepted": profile.pages_accepted,
                        "mean_wa_score": profile.mean_wa_score,
                        "total_chars": profile.total_chars,
                        "first_seen_iso": profile.first_seen_iso,
                        "last_crawled_iso": profile.last_crawled_iso,
                        "sample_url": profile.sample_urls[0] if profile.sample_urls else "",
                    }
                )

    def _write_audit_reports(self, profiles: Sequence[DomainProfile]) -> None:
        if not self._accepted_results:
            return
        rows = build_audit_rows(self._accepted_results, profiles)
        write_audit_reports(rows, csv_path=self.audit_csv_path, json_path=self.audit_json_path)

    def _build_seed_list(self) -> list[str]:
        seeds = self.load_seeds()
        if self.search_include_corpus_urls:
            seeds.extend(
                load_existing_corpus_seed_urls(
                    self.client,
                    limit=self.search_existing_corpus_seed_limit,
                )
            )
        if self.search_enabled:
            seeds.extend(self.search_seeder.discover_seed_urls())

        deduped: list[str] = []
        seen: set[str] = set()
        for seed in seeds:
            normalized = self.normalize_url(seed)
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def crawl(self, seeds: list[str]) -> list[DomainProfile]:
        checkpoint = self._load_frontier_checkpoint()
        if checkpoint:
            frontier: deque[tuple[str, int]] = checkpoint
            self._seed_domains([url for url, _depth in frontier])
        else:
            filtered_seeds = self._filter_recent_seed_urls(seeds)
            self._seed_domains(filtered_seeds)
            frontier = deque((seed, 0) for seed in filtered_seeds)

        self._seen_urls |= self._load_existing_crawled_urls()
        pages_processed = 0

        while frontier and pages_processed < self.max_total_pages:
            url, depth = frontier.popleft()
            normalized = self.normalize_url(url)
            if not normalized or normalized in self._seen_urls or depth > self.max_depth:
                continue

            domain = _canonical_domain(normalized)
            if not self.allow_external_domains and self._allowed_domains and not _root_domain_allowed(domain, self._allowed_domains):
                continue
            if self._pages_per_domain[domain] >= self.max_pages_per_domain:
                continue

            self._seen_urls.add(normalized)
            result = self.fetch_page(normalized, depth)
            if result is None:
                continue

            self._pages_per_domain[domain] += 1
            pages_processed += 1
            accepted = self._should_accept_result(result)

            profile = self._profile_for_domain(result.domain)
            profile.add_page(accepted=accepted, wa_score=result.wa_score, text=result.text, url=result.url)
            self._persist_domain_profile(profile)

            if self._should_enqueue_borderline_review(result, accepted):
                self._enqueue_borderline_review(result)

            if accepted:
                self._accepted_results.append(result)
                self._insert_result(result)

            if depth < self.max_depth:
                for link in result.links_found:
                    next_url = self.normalize_url(link)
                    if not next_url or next_url in self._seen_urls:
                        continue
                    next_domain = _canonical_domain(next_url)
                    if self._pages_per_domain[next_domain] >= self.max_pages_per_domain:
                        continue
                    if not self.allow_external_domains and self._allowed_domains and not _root_domain_allowed(next_domain, self._allowed_domains):
                        continue
                    frontier.append((next_url, depth + 1))

            if pages_processed % self.state_sync_every == 0:
                self._save_frontier_checkpoint(frontier)

        self._save_frontier_checkpoint(frontier)
        if not frontier:
            self._clear_frontier_checkpoint()

        profiles = list(self._profiles.values())
        self._write_discovery_report(profiles)
        self._write_audit_reports(profiles)
        self._persist_run_summary(profiles=profiles, frontier_remaining=len(frontier))
        return profiles

    def run(self) -> list[DomainProfile]:
        seeds = self._build_seed_list()
        return self.crawl(seeds)


def run(config: dict) -> None:
    stage_cfg = _stage_config(config)
    use_mongodb = bool((config or {}).get("database", {}).get("use_mongodb", True))

    if use_mongodb:
        with open_mongodb_client(config) as client:
            crawler = WAWebCrawler(config, client=client)
            profiles = crawler.run()
    else:
        crawler = WAWebCrawler(config, client=None)
        profiles = crawler.run()

    logger.info(
        "Web crawler finished: %d domains, %d accepted pages",
        len(profiles),
        sum(profile.pages_accepted for profile in profiles),
    )


def _load_config(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the WA web crawler")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config file")
    parser.add_argument("--print-summary", action="store_true", help="Print a JSON summary to stdout")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = _load_config(args.config)

    use_mongodb = bool((config or {}).get("database", {}).get("use_mongodb", True))
    if use_mongodb:
        with open_mongodb_client(config) as client:
            crawler = WAWebCrawler(config, client=client)
            profiles = crawler.run()
    else:
        crawler = WAWebCrawler(config, client=None)
        profiles = crawler.run()

    if args.print_summary:
        summary = {
            "domains": len(profiles),
            "pages_crawled": sum(profile.pages_crawled for profile in profiles),
            "pages_accepted": sum(profile.pages_accepted for profile in profiles),
            "discovery_report": str(crawler.discovery_report_path),
            "audit_report_csv": str(crawler.audit_csv_path),
            "audit_report_json": str(crawler.audit_json_path),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())