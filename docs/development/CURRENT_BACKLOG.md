# Current Backlog

This is the canonical short-form backlog for hytools.

- Canonical quick start: `docs/QUICK_START_PHASE1.md`
- Canonical workflow: `docs/development/DEVELOPMENT.md`
- Broader roadmap and long-tail ideas: `docs/development/FUTURE_IMPROVEMENTS.md`
- Completed work history: `docs/development/IMPLEMENTATION_HISTORY.md`

## Current priorities

### Immediate

1. Operationalize the new runner workflow in the active config.
	- Keep `hytools.ingestion.runner run --config config/settings.yaml --dry-run` as the canonical preflight check.
	- Revisit which of `incremental_merge`, `word_frequency_facets`, `drift_detection`, `export_corpus_overlap_fingerprints`, and `corpus_export` should be enabled in the default working config as rollout confidence grows.

2. Keep the completed Phase 2 aggregation hardening locked down.
	- Keep the `incremental_merge` delta and idempotency proofs green and protect them from regressions.
	- Keep the hybrid `frequency_aggregator` profile and deterministic export / release paths CI-covered.
	- Treat further work here as rollout tuning and regression prevention, not missing core implementation.

3. Build the unified review and audit layer.
	- Keep the dashboard/operator surfaces aligned with `python -m hytools.ingestion.review` as review fields evolve.
	- Keep expanding the centralized linguistics-owned heuristics as more review reasons are added.

4. Stabilize the research pipeline and make its outputs actionable.
	- Shift the next semantic-cleanup pass from author names to noisy inventory/title rows now that live author extraction is no longer persisting mixed-script OCR junk names.
	- Keep tightening title / work plausibility filters now that the live acquisition queue and dashboard detail view no longer emit known mixed-script OCR-noise titles.
	- Add any missing CLI/config overrides needed for `research_runner`, and keep the live research pipeline verified before expanding it further.
	- Add canonical author-name alias normalization so spelling, initial-only, transliterated, and OCR-variant forms resolve to the same author profile before enrichment and coverage analysis.

### Next wave

5. Connect catalog intelligence to acquisition and dedup.
	- Keep using the dashboard acquisition detail view and source-target hints to drive targeted LOC / Archive.org / Hathi / Nayiri backfill cycles.
	- Improve hit quality for LOC / Archive.org cycles and treat HathiTrust public search as 403-prone unless Hathifiles / HTRC bulk access is available.
	- Prioritize scarce or high-value WA works and reduce duplicate ingestion.

6. Expand sources in operational order, not speculative order.
	- First: make currently implemented sources fully usable in practice (DPLA, LOC, WorldCat-driven lookups, long-running OCR-first ingestion).
	- Second: permission-based sources such as Mechitarist and AGBU.
	- Third: broader OCR-first and institutional archive expansion.

7. Add one high-yield new corpus family: Western Armenian pedagogical materials.
	- Inventory curricula and publishers.
	- Scrape or OCR texts, exercises, and worksheets.
	- Preserve structure for future instruction-tuning and grammar-focused evaluation.

### After corpus expansion

8. Start the English ↔ Western Armenian translation track once the corpus and parallel-data inputs are stronger.
	- Re-scrape bilingual news sources for aligned WA/EN and EA/EN pairs.
	- Build the first translation/back-translation pipeline only after the corpus-side inputs above are in place.

9. Expand calibration and linguistic analysis once the review pipeline is stable.
	- Audit and tune the WA dialect classifier against labeled WA/EA samples.
	- Add incremental `text_metrics` backfill and other corpus-wide normalization passes.
	- Add token-level lexical-origin clustering using per-word orthographic, phonotactic, morphological, and corpus-frequency statistics so candidate non-native words are surfaced for etymology review instead of relying only on static lexicons.
	- Revisit dialect-conversion and advanced linguistic tooling only after the classifier and review loop are trustworthy.

## De-prioritized for now

- Airflow / Prefect-style orchestration beyond the local scheduler.
- Dynamic candidate discovery and always-on autonomy.
- Low-level OCR model training or custom GPU OCR efforts.
- New source expansion that depends on partnerships before current implemented sources are fully operational.

## Recently completed housekeeping

- Canonical runner/docs/workflow reconciliation for `hytools.ingestion.runner`
- Canonical quick start and development workflow docs added
- GitHub scraping workflow aligned to current stage names and command surface
- Scraper verification coverage expanded for archive_org, LOC, Wikisource, CulturaX, and Wikipedia dump handling
- Runner `doctor` and `release` command surface added and documented
- Validated config loading expanded for scraping, ingestion, export, and scheduler blocks
- Runner `--dry-run` and config-aware `list --config` verified against the active config
- Unified review queue now has a dedicated `hytools.ingestion.review` CLI and linguistics-owned review heuristics
- Research dashboard now links to an itemized detail page with acquisition backfill queries, source targets, and review rows
- Live author extraction now refreshes `author_profiles` from current extraction output instead of preserving stale OCR-noise profiles
- Mixed-script author-name corruption is now rejected during extraction, and the latest live validation run persisted a clean refreshed author profile set to MongoDB
- Mixed-script OCR-noise work titles are now filtered out of acquisition priorities, and the refreshed live queue no longer emits the known `massage`-style corruption case
- First targeted catalog backfill cycle now runs via `python -m hytools.ingestion.discovery.catalog_backfill`; the validated live pass produced Nayiri matches, kept LOC / Archive.org query-scoped, and disables HathiTrust seed-list fallback for targeted searches
