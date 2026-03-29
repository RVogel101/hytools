# Scraper Migration Gaps (Centralized Extraction Package)

## Scope used for this matrix
- Included modules with external data acquisition under `src/scraping/`:
  - `wikipedia.py`, `wikisource.py`, `archive_org.py`, `culturax.py`, `hathitrust.py`, `loc.py`, `newspaper.py`, `nayiri.py`, `eastern_armenian.py`
- Excluded non-extraction helpers/stages from primary matrix rows:
  - `runner.py` (orchestration only)
  - `metadata.py` and `metadata_tagger.py` (schema/tagging support, not source fetchers)
  - `frequency_aggregator.py` (post-processing, not scraping)
  - `loc_background_job.py`, `loc_prioritize.py` (LOC workflow wrappers)

## Key migration gaps
1. Retry/rate-limit behavior is inconsistent across scrapers.
- Strong in `src/scraping/loc.py` and `src/scraping/wikisource.py`.
- Minimal or ad hoc in `src/scraping/wikipedia.py`, `src/scraping/archive_org.py`, `src/scraping/hathitrust.py`, `src/scraping/eastern_armenian.py`.
- Selenium scrapers rely mostly on fixed sleeps rather than policy-driven backoff.

2. Output schema is not normalized.
- JSONL schemas differ by scraper (`newspaper`, `nayiri`, `culturax`, EA metadata).
- Some scrapers only emit text files and implicit metadata via file names (`wikipedia`, `hathitrust`, parts of `loc`).
- MongoDB metadata is available in `wikipedia`/`wikisource` but not generalized to others.

3. WA/EA tagging support is uneven.
- Explicit EA tagging exists in `src/scraping/eastern_armenian.py` via `TextMetadata`.
- WA tagging is often classifier-gated and optional (`archive_org`, `culturax`, `loc`, `newspaper`, `hathitrust`).
- `nayiri` is WA by source assumption but lacks explicit dialect field in outputs.

4. Endpoint declaration is fragmented.
- Some modules use explicit constants (`archive_org`, `loc`, `wikisource`, `wikipedia`).
- Others depend on config/runtime discovery (`newspaper` selectors, EA feed discovery, CulturaX through `datasets` API client).

5. Selenium dependence is concentrated and fragile.
- `src/scraping/newspaper.py` and `src/scraping/nayiri.py` depend on Chrome WebDriver and page structure assumptions.
- Anti-bot/captcha handling is limited to detection and cooldown (Nayiri), not robust automated recovery.

6. HathiTrust path is partially scaffolded.
- Search implementation logs limitations and can return an empty catalog unless manually prepared or bulk access is arranged.
- This should be marked as "limited readiness" in centralized extraction packaging.

## Recommended extraction-package contracts
1. Standardize a scraper interface.
- Required: `source_id`, `run(config)`, `discover()`, `fetch()`, `persist()`.
- Standard telemetry fields: attempts, retries, backoff_seconds, throttled, skipped_reason.

2. Enforce a normalized output envelope for all sources.
- Suggested canonical JSONL fields: `source_name`, `source_url`, `dialect`, `language_code`, `region`, `publication_date`, `extraction_date`, `content_type`, `text`, `raw_metadata`.
- Keep source-specific details inside `raw_metadata`.

3. Centralize rate limiting and retry policy.
- Shared utility for `requests` and Selenium adapters.
- Per-source policy configs (max retries, jittered backoff, crawl delay, status-code rules).

4. Separate dialect decision from scraper transport.
- Explicit dialect/tagging stage for both WA and EA.
- Preserve current classifier-based WA filtering as optional pre/post hook.

5. Capture endpoint registry in one place.
- Per-source endpoint manifest (including discovered or template endpoints) for governance and migration planning.

## Notable modules to fold in later (outside `src/scraping`)
- `ingestion/discovery/worldcat_searcher.py`: external search integration (requests-based) with useful bibliographic metadata, part of ingestion discovery/book-inventory pipeline.
