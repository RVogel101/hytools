# Scraping Runner and LOC Design

## Architecture Overview

The scraping pipeline is **centralized** in `scraping.runner`. All data-acquisition and processing stages run sequentially through this single entry point:

- **Wikimedia**: wikipedia_wa, wikipedia_ea, wikisource  
- **Digital libraries**: archive_org, hathitrust, gallica, **loc**, **dpla**  
- **News**: newspaper, ea_news, rss_news  
- **Datasets**: culturax, english_sources  
- **Reference**: nayiri, gomidas, **mechitarist**, **agbu**, ocr_ingest, mss_nkr, worldcat_searcher  
- **Post-processing**: **cleaning** (cleaning.run_mongodb), metadata_tagger, frequency_aggregator  
- **Extraction**: import_anki_to_mongodb, validate_contract_alignment, materialize_dialect_views, summarize_unified_documents  

**CLI:** `python -m scraping.runner run | status | list | dashboard`

## Why LOC Is in the Runner

LOC is a **normal stage** in the pipeline, alongside archive_org, hathitrust, and gallica. It is not a separate "background" process by design:

- **Same contract**: LOC has `run(config)` like other scrapers
- **Same runner**: `python -m scraping.runner run` runs LOC when the `loc` stage is enabled
- **MongoDB-only**: LOC writes to MongoDB; no local JSON/txt storage

LOC is included because it is one of the primary digital library sources for Western Armenian texts.

## Background Modes

Two levels of background execution exist:

### 1. Full pipeline in background

```bash
python -m scraping.runner run --background
```

Runs the entire pipeline (including LOC) in a detached process. Logs go to `data/logs/pipeline_runner.log`.

### 2. LOC-only in background

```bash
python -m scraping.loc run --background
```

Runs the LOC stage alone in background. Useful when you want to:

- Run only LOC scraping without other stages
- Use LOC's separate CLI (`catalog`, `status`, `clean`)

LOC has its own CLI because it has special needs:

- **catalog**: Manage catalog in MongoDB (clean malformed IDs, show status)
- **status**: Show progress from log files
- **catalog --clean**: Filter invalid item IDs

## Centralization

Background processes are **centralized** in the runner:

- **Full pipeline background**: Use `scraping.runner run --background`
- **Single-stage background**: Use `scraping.<stage> run --background` (e.g. LOC)

Both spawn the same underlying process; the runner just orchestrates all stages. For CI, cron, or systemd, prefer the runner:

```bash
python -m scraping.runner run --background
```

## Stage Names

Stage names for `--only` and `--skip` (and `--group` when used) match the runner’s `_build_stages()`:

- **Wikimedia:** wikipedia_wa, wikipedia_ea, wikisource  
- **Digital libraries:** archive_org, hathitrust, gallica, loc, dpla  
- **News:** newspaper, ea_news, rss_news  
- **Datasets:** culturax, english_sources  
- **Reference:** nayiri, gomidas, mechitarist, agbu, ocr_ingest, mss_nkr, worldcat_searcher  
- **Post-processing:** cleaning, metadata_tagger, frequency_aggregator, export_corpus_overlap_fingerprints  
- **Extraction:** import_anki_to_mongodb, validate_contract_alignment, materialize_dialect_views, summarize_unified_documents  

**Dashboard:** `python -m scraping.runner dashboard [--output data/logs/scraper_dashboard.html]` generates static HTML with document counts by source and word frequency summary. Requires MongoDB.

For CI, cron, or systemd, prefer the full runner; use `--group scraping`, `--group extraction`, or `--group postprocessing` to run predefined stage subsets (see `runner.py` for the exact list per group).
