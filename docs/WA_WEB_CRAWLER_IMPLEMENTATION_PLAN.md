# WA Web Discovery Crawler — Implementation Plan

**Status**: IMPLEMENTED
**Date**: 2026-03-06
**Builds on**: `docs/concept_guides/western_armenian_web_crawler.md`

## Implementation Status

The phased implementation described below is now present in the codebase:
- `hytools/ingestion/acquisition/web_crawler.py` implements the core crawler, MongoDB integration, incremental state, CSV discovery reporting, and optional Playwright fallback.
- `hytools/ingestion/acquisition/search_seeder.py` implements DuckDuckGo search seeding plus existing-corpus URL seeding.
- `hytools/ingestion/acquisition/wa_crawler_audit.py` implements per-domain audit report generation.
- `hytools/ingestion/runner.py` and `config/settings*.yaml` include the new `web_crawler` stage and configuration.
- `tests/test_web_crawler.py` covers the crawler, seeder, audit output, and runner registration.

## Objective

Implement a modular Western Armenian web discovery crawler that finds,
evaluates, and harvests WA content from the open web.  Integrates with
existing hytools ingestion pipeline, MongoDB storage, and WA dialect classifier.

## Recommended Approach: Hybrid (Option A + B)

Combine a targeted BFS crawler with DuckDuckGo search seeding. This gives:
- DuckDuckGo queries for breadth (discover new domains fast, free, no API key)
- Direct crawl for depth (harvest full content from discovered sites)
- Existing WA classifier for filtering

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Seed Sources                        │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │ Static seed│  │ DuckDuckGo   │  │ Existing     ││
│  │ list (.txt)│  │ (free, no key│  │ corpus URLs  ││
│  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘│
│        └────────────┬────┘─────────────────┘        │
│                     ▼                                │
│              URL Frontier                            │
│        (priority queue + dedup)                      │
│                     │                                │
│                     ▼                                │
│         ┌───────────────────┐                        │
│         │   Page Fetcher    │                        │
│         │ requests + robots │                        │
│         │ + rate limiter    │                        │
│         └────────┬──────────┘                        │
│                  │                                   │
│         ┌────────▼──────────┐                        │
│         │  Content Parser   │                        │
│         │  BS4 text extract │                        │
│         └────────┬──────────┘                        │
│                  │                                   │
│         ┌────────▼──────────┐                        │
│         │  Armenian         │                        │
│         │  Classifier       │                        │
│         │  Armenian script? │                        │
│         │  WA/EA classify   │                        │
│         │  Dialect tag      │                        │
│         └────────┬──────────┘                        │
│                  │                                   │
│        ┌─────────┴──────────┐                        │
│        ▼                    ▼                        │
│  Armenian >= 10%       Armenian < 10%                │
│  ┌──────────┐         ┌──────────┐                   │
│  │ Accept   │         │ Reject   │                   │
│  │→ classify│         │→ log only│                   │
│  │→ MongoDB │         └──────────┘                   │
│  └──────────┘                                        │
└─────────────────────────────────────────────────────┘
```

## Module Layout

```
hytools/ingestion/acquisition/web_crawler.py    # Core crawler
hytools/ingestion/acquisition/search_seeder.py  # DuckDuckGo search seeding (free, no API key)
hytools/ingestion/acquisition/wa_crawler_audit.py # Audit/report utilities
data/retrieval/crawler_seeds.txt                # Static seed URLs
data/retrieval/crawler_found.csv                # Discovered WA sites (output)
tests/test_web_crawler.py                       # Unit tests
docs/concept_guides/western_armenian_web_crawler.md  # (existing design doc)
```

## `web_crawler.py` — Core Crawler Module

### Classes

```python
@dataclass
class CrawlResult:
    """Single page crawl result."""
    url: str
    domain: str
    depth: int
    status_code: int
    text: str                    # extracted body text
    title: str
    armenian_char_ratio: float   # % of Armenian script chars
    wa_score: float              # Western Armenian dialect score
    links_found: list[str]       # outgoing links for frontier
    fetch_time_ms: int
    robots_allowed: bool

@dataclass
class DomainProfile:
    """Aggregated stats for a discovered domain."""
    domain: str
    pages_crawled: int
    pages_accepted: int
    mean_wa_score: float
    total_chars: int
    first_seen_iso: str
    last_crawled_iso: str
    sample_urls: list[str]       # up to 5 representative pages

class WAWebCrawler:
    """BFS web crawler with WA dialect scoring."""

    def __init__(
        self,
        config: dict,
        *,
        seed_file: Path | None = None,
        max_depth: int = 2,
        max_pages_per_domain: int = 50,
        request_delay: float = 2.0,    # seconds between requests to same domain
        wa_threshold: float = 0.55,
        user_agent: str = "HytoolsCorpusCrawler/1.0 (+https://github.com/...)"
    ): ...

    def load_seeds(self) -> list[str]: ...
    def check_robots(self, url: str) -> bool: ...
    def fetch_page(self, url: str) -> CrawlResult | None: ...
    def score_page(self, text: str) -> tuple[float, float]: ...  # (armenian_ratio, wa_score)
    def crawl(self, seeds: list[str]) -> list[DomainProfile]: ...
    def run(self, config: dict) -> None: ...  # Pipeline entry point
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HTTP client | `requests` + `urllib.robotparser` | Already in deps, sufficient for MVP |
| Parser | `BeautifulSoup` (lxml) | Already used in news.py |
| WA scoring | `branch_dialect_classifier.classify_text()` | Existing classifier, no new model needed |
| Rate limiting | Per-domain delay (configurable) | Respectful crawling; `time.monotonic()` tracking |
| URL dedup | Normalized URL set (scheme://domain/path) | Prevents re-crawling same content |
| Storage | `insert_or_skip()` → MongoDB `documents` | Reuses existing pipeline infrastructure |
| Frontier | `collections.deque` with `(url, depth)` | Simple BFS; no external queue needed for MVP |

### robots.txt Compliance

```python
from urllib.robotparser import RobotFileParser

def check_robots(self, url: str) -> bool:
    domain = urlparse(url).netloc
    if domain not in self._robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"https://{domain}/robots.txt")
        try:
            rp.read()
        except Exception:
            pass  # allow if robots.txt unreadable
        self._robots_cache[domain] = rp
    return self._robots_cache[domain].can_fetch(self.user_agent, url)
```

### Armenian Classification Integration

All Armenian text is accepted — both Western and Eastern — and
tagged with the correct dialect classification.

```python
def classify_page(self, text: str) -> dict | None:
    """Classify Armenian page. Returns metadata dict or None to reject."""
    if not text:
        return None

    # Step 1: Armenian script ratio
    arm_chars = sum(1 for c in text if '\u0531' <= c <= '\u058F')
    total_chars = len(text.strip())
    arm_ratio = arm_chars / max(total_chars, 1)

    if arm_ratio < 0.10:  # <10% Armenian script → reject
        return None

    # Step 2: Dialect classification using existing classifier
    from hytools.linguistics.dialect.branch_dialect_classifier import (
        classify_text_classification,
    )
    result = classify_text_classification(text)
    label = result.get("label", "inconclusive")
    western = result.get("western_score", 0.0)
    eastern = result.get("eastern_score", 0.0)
    classical = result.get("classical_score", 0.0)

    # Map to internal_language_branch
    if label == "likely_western":
        branch = "hye-w"
        lang_code = "hy"
    elif label == "likely_eastern":
        branch = "hye-e"
        lang_code = "hy"
    else:
        branch = None
        lang_code = "hy"  # still Armenian, just inconclusive dialect

    return {
        "armenian_char_ratio": round(arm_ratio, 4),
        "internal_language_code": lang_code,
        "internal_language_branch": branch,
        "dialect_label": label,
        "western_score": western,
        "eastern_score": eastern,
        "classical_score": classical,
    }
```

## Seed File Format

```
# data/retrieval/crawler_seeds.txt
# Lines starting with # are comments.  One URL per line.

# Diaspora newspapers (already scraped, but may have sub-pages)
https://aztagdaily.com
https://horizonweekly.ca/am
https://asbarez.am
https://hairenik.com
https://armenianweekly.com
https://keghart.com

# Community organizations
https://agbu.org
https://hamazkayin.com

# Church / religious
https://armenianprelacy.org
https://armenianchurch.org

# Cultural / educational
https://arak29.am
https://armenianhouse.org
https://aniarc.am

# Forums / social
https://hayastan.com

# Wikimedia
https://hyw.wikipedia.org
https://hy.wikisource.org

# Literature archives
https://tert.nla.am
https://greenstone.flib.sci.am

# Diaspora media (additional)
https://armenianlife.com
https://norashkharhik.com
https://bolsahye.com
```

## Pipeline Integration

### Runner Stage

```python
# In runner.py _build_stages():
Stage("web_crawler", "hytools.ingestion.acquisition.web_crawler",
      enabled=_on("web_crawler"), supports_mongodb=True),
```

### Config

```yaml
# config/settings.yaml
ingestion:
  web_crawler:
    enabled: false           # Opt-in for now
    max_depth: 2
    max_pages_per_domain: 50
    request_delay_seconds: 2.0
    wa_threshold: 0.55
    seed_file: "data/retrieval/crawler_seeds.txt"
```

## Output

### MongoDB Documents

Each accepted page produces a standard document:

```json
{
    "source": "web_crawler",
    "title": "Արdelays Մասնdelays Article Title",
    "text": "Full extracted text...",
    "url": "https://example.com/page",
    "metadata": {
        "source_language_code": "hyw",
        "internal_language_branch": "hye-w",
        "wa_score": 0.82,
        "armenian_char_ratio": 0.91,
        "domain": "example.com",
        "crawl_depth": 1,
        "crawler_version": "1.0"
    }
}
```

### Discovery Report

```csv
# data/retrieval/crawler_found.csv
domain,pages_crawled,pages_accepted,mean_wa_score,total_chars,first_seen,sample_url
aztagdaily.com,48,42,0.87,245000,2026-03-06,https://aztagdaily.com/article/123
```

## Implementation Phases

Each phase is self-contained — it delivers working functionality on its own
and does NOT depend on later phases being completed.

### Phase Overview

| Phase | Scope | Output | Depends On |
|-------|-------|--------|------------|
| **MVP** | BFS crawler + Armenian classification + static seeds | `web_crawler.py` + seed list | Nothing — standalone |
| **v1** | MongoDB storage + runner stage + config + `ScrapedDocument` | Full pipeline integration | MVP |
| **v2** | DuckDuckGo search seeding + incremental crawl state in MongoDB | `search_seeder.py` + `crawler_state` collection | v1 |
| **v3** | Playwright fallback for JS-rendered sites + quality audit | `wa_crawler_audit.py` | v1 |

---

### MVP — Core Crawler (start here)

**Goal**: Crawl a static list of known Armenian sites, extract text, classify
dialect, produce a CSV discovery report.

**What gets built**:
- `WAWebCrawler` class with BFS frontier, robots.txt compliance, rate limiting
- Two-phase content extraction (`_extract_text`) with boilerplate removal
- `classify_page()` — accepts WA + EA, tags dialect via `classify_text_classification()`
- Static seed URL list (hand-picked known Armenian domains)
- CSV output: `data/retrieval/crawler_found.csv` (domain profiles)
- Security: SSRF protection, response size cap, content-type allowlist, HTTPS enforcement

**What is NOT included**: No MongoDB, no pipeline runner, no search API, no JS rendering.

**How to run**: Direct Python invocation — `python -m hytools.ingestion.acquisition.web_crawler`

---

### v1 — Pipeline Integration

**Goal**: Wire the crawler into the existing ingestion pipeline so crawled
pages are stored in MongoDB using `ScrapedDocument` + `insert_or_skip()`.

**What gets built**:
- MongoDB storage via `ScrapedDocument` (auto-computes linguistics, dialect scores)
- Runner stage registration (`Stage("web_crawler", ...)` in `runner.py`)
- `config/settings.yaml` section: enable/disable, thresholds, depth, delay
- Domain profile storage in MongoDB (replaces CSV-only output)

**Depends on**: MVP crawler working end-to-end.

---

### v2 — Search Seeding + Incremental Mode

**Goal**: Discover new Armenian domains automatically via DuckDuckGo queries.
Resume crawls without re-visiting already-crawled pages.

**What gets built**:
- `search_seeder.py` — curated DuckDuckGo query templates (Armenian keywords,
  WA/EA vocabulary, diaspora terms, `.am` TLD sweeps)
- Feeds discovered URLs into the URL frontier as new seeds
- `crawler_state` MongoDB collection — stores `last_crawled` per domain,
  frontier checkpoint, crawl progress (no local files)
- Incremental crawl: skip domains crawled within configurable window

**Depends on**: v1 (MongoDB storage must be working).

---

### v3 — JS Rendering + Quality Audit

**Goal**: Handle the minority of Armenian sites that require JavaScript
rendering. Audit corpus quality across all crawled domains.

**What gets built**:
- Playwright-based fallback fetcher for JS-rendered pages
- `wa_crawler_audit.py` — per-domain quality report (WA purity, noise ratio,
  boilerplate leakage, dialect distribution)
- Automatic detection of JS-required sites (empty body from `requests` → retry with Playwright)

**Depends on**: v1 (pipeline integration). Independent of v2.

## Test Plan

```python
class TestWAWebCrawler:
    def test_check_robots_allowed(self): ...
    def test_check_robots_disallowed(self): ...
    def test_score_page_western_armenian(self): ...
    def test_score_page_eastern_armenian(self): ...
    def test_score_page_non_armenian(self): ...
    def test_url_normalization_dedup(self): ...
    def test_respect_max_depth(self): ...
    def test_respect_max_pages_per_domain(self): ...
    def test_rate_limit_between_requests(self): ...
    def test_domain_profile_aggregation(self): ...
    def test_load_seeds_from_file(self): ...
    def test_crawl_result_to_insert_dict(self): ...
```

## Safety and Compliance

- **robots.txt**: Always checked before fetch. Denied = skip.
- **User-Agent**: Clearly identifies crawler + contact URL.
- **Rate limiting**: Configurable per-domain delay (default 2s).
- **Max depth/pages**: Hard limits prevent runaway crawling.
- **No PII collection**: Text extraction only, no form data or auth pages.
- **Blocklist**: Reuse `RSS_BLOCKED_SOURCES` from news.py for domain filtering.

## Security Hardening

The crawler fetches arbitrary HTML from the open web. The following
defences ensure no malicious content reaches the local system or the
corpus database.

### Threat Model

| Threat | Vector | Mitigation |
|--------|--------|------------|
| Malicious JavaScript | `<script>` tags, `on*` event handlers, `javascript:` URIs | BS4 text extraction strips all tags — no JS is ever executed |
| Drive-by download links | `<a href="malware.exe">`, `<meta http-equiv="refresh">` | Only `.text` of parsed HTML is stored; links used only for URL frontier, never opened/downloaded |
| Embedded malware in HTML | Encoded payloads in comments, data-URIs, base64 blobs | `BeautifulSoup.get_text()` discards all non-text nodes; content-type allowlist rejects non-`text/html` responses |
| Malicious redirects | 30x chains to phishing/exploit pages | `requests` follows max 5 redirects (default); final URL domain checked against seed domain allowlist |
| Decompression bombs (zip bombs) | Huge `Content-Encoding: gzip` payloads | Hard cap on response size (`max_response_bytes`, default 5 MB) via `stream=True` + chunked read |
| Server-Side Request Forgery (SSRF) | Seed URLs pointing to `localhost`, `169.254.x.x`, internal IPs | URL validation rejects private/loopback/link-local IPs before fetch |
| Hostile robots.txt / sitemap | Oversized files, infinite loops | Timeout on robots.txt fetch (5s); size cap (512 KB) |
| Stored XSS via corpus DB | Malicious text injected into MongoDB, rendered later | All stored text is plain-text (no HTML); downstream consumers must escape on display |
| SSL/TLS downgrade | MITM on HTTP connections | Enforce HTTPS-only by default; optional `allow_http=False` config flag |

### Implementation Checklist

```python
# 1. Response size cap — prevents decompression bombs
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB

def _safe_fetch(self, url: str) -> requests.Response | None:
    resp = self._session.get(url, stream=True, timeout=(5, 30))
    content = b""
    for chunk in resp.iter_content(chunk_size=8192):
        content += chunk
        if len(content) > MAX_RESPONSE_BYTES:
            logger.warning("Response too large, aborting: %s", url)
            resp.close()
            return None
    resp._content = content
    return resp

# 2. Content-type allowlist — reject non-HTML responses
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}

def _is_html(self, resp: requests.Response) -> bool:
    ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return ct in ALLOWED_CONTENT_TYPES

# 3. SSRF protection — block private/internal IPs
import ipaddress, socket

def _is_safe_url(self, url: str) -> bool:
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                logger.warning("Blocked private/internal IP: %s → %s", url, addr)
                return False
    except socket.gaierror:
        return False
    return True

# 4. Two-phase content extraction — strips boilerplate, then extracts text
def _extract_text(self, html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # Phase 0: Decompose dangerous and non-content tags
    for tag in soup.find_all([
        "script", "style", "noscript", "iframe", "object", "embed",
        "nav", "header", "footer", "aside",
    ]):
        tag.decompose()
    # Also remove [role=navigation], cookie banners, social share bars
    for tag in soup.select("[role=navigation], .cookie-banner, .social-share, "
                           ".share-buttons, .sidebar, .widget, .ad, .advertisement"):
        tag.decompose()

    # Phase 1: Extract from semantic content tags only
    paragraphs = []
    for tag in soup.find_all(["p", "li", "blockquote", "h1", "h2", "h3", "h4"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) >= 15:  # skip tiny fragments (buttons, labels)
            paragraphs.append(txt)
    body = "\n\n".join(paragraphs).strip()
    if len(body) >= 200:
        return body

    # Phase 2: Fallback — full text extraction (for non-semantic sites)
    full = soup.get_text("\n", strip=True)
    full = re.sub(r"\n{3,}", "\n\n", full).strip()
    return full

# 5. URL scheme enforcement
def _is_allowed_scheme(self, url: str) -> bool:
    return urlparse(url).scheme in ("https", "http")  # no javascript:, data:, file:
```

### Dangerous Content Never Stored

The pipeline stores **only plain text** extracted via `BeautifulSoup.get_text()`.
No raw HTML, no `<script>` tags, no binary data, no embedded objects ever
reach MongoDB. The text extraction acts as a one-way sanitisation gate:

```
Raw HTML  →  BS4 parse  →  decompose dangerous tags  →  .get_text()  →  plain text only  →  MongoDB
```

Even if a page contains obfuscated malware in HTML comments or data-URIs,
`get_text()` discards all of it. The stored corpus is inert plain text.

## Content Extraction & Cleaning Pipeline

Web pages contain navigation bars, buttons, ribbons, cookie banners, social
share widgets, sidebars, ads, and footer links surrounding the actual article
content. The crawler must strip all of this boilerplate before storing text.

### Extraction Strategy: Two-Phase (proven pattern)

This matches the approach already used by `hamazkayin.py` and `jw.py` scrapers.

```
Raw HTML
  │
  ▼
Phase 0: Decompose non-content tags
  ├── <script>, <style>, <noscript>, <iframe>, <object>, <embed>
  ├── <nav>, <header>, <footer>, <aside>
  ├── [role=navigation], .cookie-banner, .sidebar, .widget
  └── .social-share, .share-buttons, .ad, .advertisement
  │
  ▼
Phase 1: Semantic tag extraction (preferred)
  Extract text from: <p>, <li>, <blockquote>, <h1>-<h4>
  Filter: discard fragments < 15 chars (buttons, labels, icons)
  Join with double newlines
  │
  ├── body >= 200 chars? → DONE (clean article text)
  │
  ▼
Phase 2: Fallback full-page extraction
  soup.get_text("\n", strip=True)
  Collapse 3+ consecutive newlines to 2
  → Return full text (less structured sites)
```

### What Gets Removed (boilerplate examples)

| HTML Element | Example Content | Removed By |
|---|---|---|
| `<nav>` | "Home \| About \| Contact" | Phase 0 decompose |
| `<header>` | Site logo, language switcher | Phase 0 decompose |
| `<footer>` | Copyright, social links | Phase 0 decompose |
| `<aside>` | Related articles, sidebar widgets | Phase 0 decompose |
| `<script>` | Google Analytics, ad scripts | Phase 0 decompose |
| `.cookie-banner` | "Accept cookies" button | Phase 0 CSS selector |
| `.social-share` | Facebook/Twitter share buttons | Phase 0 CSS selector |
| `.sidebar` | Category lists, tag clouds | Phase 0 CSS selector |
| `.ad` / `.advertisement` | Banner ads, sponsored content | Phase 0 CSS selector |
| Small `<p>` (< 15 chars) | "Read more", "Share", "Print" | Phase 1 length filter |

### Post-Extraction Cleaning

After text extraction, before storage via `ScrapedDocument`:

1. **Unicode normalisation**: NFC form (consistent Armenian character representation)
2. **Whitespace collapse**: Multiple spaces → single space, 3+ newlines → 2
3. **Minimum length check**: Pages with < 200 chars of extracted text are rejected
4. **Armenian script ratio**: Must be ≥ 10% Armenian characters to qualify
5. **Dialect classification**: `classify_text_classification()` tags as WA/EA/classical
6. **Standard linguistics**: `compute_standard_linguistics()` auto-fills quantitative
   metrics (char_count, word_count, TTR, entropy, etc.) via `ScrapedDocument`

### Existing Scraper Patterns (reference)

| Scraper | Extraction Method | Boilerplate Removal |
|---|---|---|
| `hamazkayin.py` | Two-phase: semantic tags → full text | ✅ nav, header, footer, aside, script, style |
| `jw.py` | Two-phase: `<article>` → all `<p>` | ✅ nav, header, footer, aside, script, style |
| `news.py` | CSS selector priority (`.entry-content p`, etc.) | ❌ Relies on CSS targeting |
| `wiki.py` | XML dump + wikitext cleaning | ✅ Wikitext-specific |
| `archive_org.py` | Pre-extracted DjVuTXT / ABBYY | N/A (no HTML) |
| `loc.py`, `dpla.py`, `gallica.py` | JSON API responses | N/A (no HTML) |

The web crawler uses the same two-phase approach as `hamazkayin.py` — the most
thorough boilerplate removal pattern in the codebase.

## Open Questions

1. ~~**Search API choice**~~: **RESOLVED** — DuckDuckGo via `duckduckgo-search`
   Python package. Free, no API key, no rate limit, sufficient for targeted
   domain-discovery queries. Fallback: Common Crawl CDX index for bulk
   URL discovery offline.

2. ~~**Headless browser**~~: **RESOLVED** — Defer to v3. Most WA sites are
   server-rendered; `requests` suffices for MVP. Playwright added later only
   if JS-rendered sites are discovered.

3. ~~**Incremental mode**~~: **RESOLVED** — Use MongoDB. Store `last_crawled`
   and crawler state in a `crawler_state` collection in the same MongoDB
   database. No local files. Domain profiles, crawl progress, and
   frontier checkpoints all live in MongoDB for consistency and portability.
