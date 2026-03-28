# Western Armenian Web Crawler (hytools)

## Overview

This document describes a complete design for a Western Armenian website discovery crawler, including
- seed source strategy
- crawler architecture
- dialect/language filtering
- scoring and content validation
- pros/cons, effort estimates, and recommended integration points with existing hytools and WesternArmenianLLM pipelines.

The goal is to find and harvest Western Armenian (hye-w) web content suitable for corpus expansion.

---

## 1. Use Cases

1. Add new Western Armenian domains to corpus
2. Automate discovery from open web using orthography heuristics
3. Ground future RAG and training data in web provenance
4. Detect site-level Eastern vs Western usage and prioritize Western

---

## 2. Crawler Architecture

### 2.1. Seed sources

- curated list of known Western Armenian domains (initial)
- diaspora community sites, forum archives, publications
- search engine driven seeds (Bing/Google APIs by WA keywords)
- existing local sources from repo data (`WesternArmenianLLM/data`, `hytools/data`)

### 2.2. URL frontier and crawl policy

- BFS/priority queue; track depth and domain
- per-domain rate limit (e.g., 1 req/s or 1 req/2s)
- `robots.txt` parser and policy adherence
- max depth (2-3) for site discovery; per-site page limit (e.g., 100)
- duplicate prevention by normalized URL (scheme/domain/path query sort)

### 2.3. Content fetch and parse

- HTTP client: `requests`/`httpx`, timeout, retries
- parse with `BeautifulSoup` for text extraction
- optionally integrate headless browser fallback (`playwright`) for JS-heavy pages

### 2.4. Language detection and WA scoring

- Armenian script test: `re.search(r"[\u0531-\u058F]", text)`
- high-confidence WA heuristics:
  - Western-specific lexicon coverage
  - Western orthography tokens vs Eastern tokens
  - manual ratios by word lists
- optional model-based classifier: existing `hytools.linguistics` or a new model

### 2.5. Storage and pipeline

- store raw page + metadata in `data/retrieval` with chain of provenance
- generate site-level record:
  - source_url, domain, `source_type`, `score`, `language`, `dialect`, `last_crawled`
- feed into existing data pipeline `hytools/ingestion` for normalization/dedup

---

## 3. Workflows

### 3.1 Discovery-only workflow

1. Get seeds from static config (`crawler_seeds.txt`) and search API.
2. Crawl 1-2 depth; keep URLs that pass WA scoring.
3. Export list for manual review and pipeline ingestion.

### 3.2 Harvest workflow (data ingestion)

1. For each trusted site, crawl full text up to 100 pages.
2. Run WA filter and split into raw-saved docs.
3. Dedup + clean with `hytools` ingestion.
4. Add to training corpus dataset.

### 3.3 Automation schedule

- weekly (good enough) `cron`/GitHub Actions run
- daily for high-priority domains
- incremental updates via `last_crawled` timestamp

---

## 4. Implementation Plan

### 4.1 Minimal viable (MVP): discovery
- script: `scripts/wa_crawler_discovery.py`
- tasks: seed list > crawl > filter > output `data/wa_crawler/seeds_found.csv`
- test on 10 domain seeds

### 4.2 Full harvest (v1)
- script: `scripts/wa_crawler_harvest.py`
- tasks: crawl + store raw text + call existing ingestion path
- avoid duplicates with SHA256 normalized text

### 4.3 Quality guard
- script: `scripts/wa_crawler_audit.py`
- tasks: sample pages, compute WA/Eastern ratios, generate report

---

## 5. Pros & Cons

### Option A: direct web crawl (own spider)

Pros:
- full control over heuristics and provenance
- can run closed loop for your dialect criteria
- no API rate limits (except target sites)

Cons:
- higher engineering and maintenance burden
- potential robot/tos/legal risk if misconfigured
- may have more duplicate / low-quality output

Effort: medium-high (3-4 dev days) + maintenance

### Option B: search API discovery + filtering (hybrid)

Pros:
- quickly find candidate domains without deep crawling
- fewer trap pages and spam risk
- easier to maintain (no full spider logic)

Cons:
- Depends on external API quotas/cost
- still requires WA filtering and validation

Effort: medium (1-2 dev days) + API cost management

### Option C: manual data source curation + incremental scraping

Pros:
- highest precision / minimal false positives
- fits existing workflow without heavy new crawler

Cons:
- slower expansion, more manual effort
- less scalable for unknown domains

Effort: low-medium (1 dev day + manual curation)

---

## 6. Dialect score model (optional for boosting)

- define known Western/Eastern token sets from corpus (e.g. `western_lexicon.txt`, `eastern_lexicon.txt`)
- compute ratio per document:
  - `western_count / (western_count + eastern_count)`
- accept pages with score >= 0.60 (tunable)

### 6.1 Seed lexicon audition

- use existing WA lexicon from `hytools/data` + Anki DB
- map common function words in WA

---

## 7. Integration with current hytools modules

- ingestion module: `hytools/ingestion/acquisition/` (contains current scrapers)
- sensor module: `hytools/linguistics` for language tags
- database join: `hytools/data/retrieval/` and `WesternArmenianLLM/data/retrieval`

## 8. Suggested docs updates

- add this new doc to `docs/INDEX.md` as `Western Armenian web crawler spec`
- add `scripts/run_waterman_crawler.sh` wrapper for local run

---

## 9. Next Step (execute)

1. Create `crawler_seeds.txt` in `data/retrieval` with 25 known domains.
2. Implement MVP script + tests under `tests/`.
3. Validate output with existing clean pipeline.
4. Iterate scoring model.
