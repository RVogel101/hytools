# hytools Always-On Data Pipeline Architecture

## Objective

Create an always-on data collection and processing pipeline for Western Armenian content, with automated discovery, acquisition, language tagging, cleaning, de-duplication, splitting, and monitoring.

The pipeline should be robust, fault-tolerant, maintainable, and track provenance and quality metrics throughout.

---

## 1. System components

### 1.1. Discovery layer

- **Source types**
  - Web crawler (`docs/western_armenian_web_crawler.md`)
  - RSS/Atom feed watcher
  - Search API (Google/Bing) with WA query templates
  - Manual curated source list
- **Output**: candidate URLs and sources dataset.

### 1.2. Acquisition layer

- **Downloader workers**
  - `requests`/`httpx` fetcher, optional `playwright` for JS-loaded content
- **Support formats**
  - HTML pages
  - PDFs/EPUBs → OCR pipeline
  - Images with Armenian text → OCR
- **Metadata**
  - `source_url`, `domain`, `crawl_time`, `http_status`, `content_type`, `robot_policy`

### 1.3. Language tagging & dialect scoring

- Existing module: `hytools.linguistics.language_tagging.*`
- Add Western/Eastern dialect score:
  - `western_tokens`, `eastern_tokens`, `token_ratio`
- Score thresholds and gating (e.g., keep `p_western > 0.55`)
- Mark borderline for manual review.

### 1.4. Clean / normalize layer

- Unicode: `NFKC`, Persian/Latin stripping, whitespace normalization,
- Orthography: Western-specific mapping, hand-coded rules.
- Remove common noise blocks (nav, footer, ads, comments) with heuristics.
- Document-level language and length filters.

### 1.5. Dedup / merge layer

- Normalized text hash (SHA256) dedupe key.
- Near-duplicate detection via MinHash or token Jaccard.
- Source prioritization: prefer canonical sites.
- Batch dedupe and daily dedupe.

### 1.6. Split & store layer

- Data buckets:
  - `train`, `val`, `test`, `review`, `archive`
- Output formats:
  - `jsonl`, `parquet`, Mongo/SQL ingest
- Provenance fields:
  - `source_url`, `source_domain`, `crawl_date`, `pipeline_version`, `dialect_score`

---

## 2. Orchestration & automation

### 2.1. Orchestrator choices

- Airflow / Prefect / Dagster (recommended heavy) or
- lightweight: cron + custom controller script (`scripts/runner_data_pipeline.py`)

### 2.2. Event-driven architecture

- Use **queues**:
  - Redis, RabbitMQ, or Kafka for task distribution
- **Workers** for each stage:
  - `discover_worker`, `download_worker`, `language_worker`, `clean_worker`, `dedupe_worker`, `store_worker`
- State store for tasks:
  - local DB / Mongo with `task_id`, `status`, `retry_count`, `last_update`

### 2.3. Continuous run

- Scheduler triggers:
  - periodic ticks (cron or DAG schedule)
  - event triggers (new feed item, new candidate URL)
- Concurrency limits per domain
- Backoff for errors (5xx statuses 1m, 429 5m)

---

## 3. Monitoring and quality assurance

### 3.1. Key metrics

- ingestion throughput (pages/hr)
- URL acceptance rate
- WA/EA tag ratio
- dedupe rate
- good/failed task counts
- latency per step

### 3.2. Alerts

- no WA pages for 24h -> alert
- pipeline failures > 5 per hour
- source blacklist triggers

### 3.3. Human-in-loop review

- review queue for low-confidence items
- manual tag corrections can update model/lexicon
- periodic audit sampling (e.g., 1% of data)

---

## 4. Roadmap (phased implementation)

### Phase 1: Baseline batch pipeline

- implement and run manually
- confirm data path and cleaning
- docs: `docs/data_pipeline.md`, `docs/western_armenian_web_crawler.md`

### Phase 2: Basic automation

- schedule via cron/systemd
- maintain state files and logs
- build minimal queue + retry logic

### Phase 3: Full orchestrated pipeline

- integrate with workflow manager (Airflow/Prefect)
- add modular workers
- add monitoring stack

### Phase 4: Always-on autonomy

- add dynamic candidate discovery + live updates
- automatically retrain dialect model from new review data
- implement self healing and backfill

---

## 5. Integration with existing hytools structure

- place impl under `hytools/ingestion/acquisition/` for crawlers
- place core pipeline modules under `hytools/ingestion/cleaning/`, `hytools/ingestion/dedupe/`
- add `scripts/` orchestrator entrypoint
- use `hytools/data` for storage and `hytools/docs` for docs

---

## 6. Nonfunctional requirements

- security: avoid PII collection, adhere to terms of service
- compliance: robots.txt, `User-Agent`, request throttling
- observability: structured logs, tracing tags, error context
- maintainability: modular, pluggable, test coverage

---

## 7. Documentation links

- `docs/western_armenian_web_crawler.md`
- `docs/data_pipeline.md`
- `docs/hytools_always_on_data_pipeline.md`
- change log and status docs in `docs/IMPLEMENTATION_HISTORY.md`
