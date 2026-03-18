# Test Run Checklist — Data Collection Pipeline

Use this to run a first end-to-end test of the scraping and post-processing pipeline.

---

## 1. Prerequisites

| Requirement | Check |
|-------------|--------|
| **Python 3.10+** | `python --version` |
| **MongoDB running** | `mongosh --eval "db.adminCommand('ping')"` (or MongoDB Compass / service running on `localhost:27017`) |
| **Config** | `config/settings.yaml` exists (copy from repo; your current file has paths + database + ingestion (or scraping) sections) |
| **Install** | From repo root: `pip install -e ".[mongodb,rss,browser,huggingface]"` (or `.[all]` for everything) |

Optional for specific stages:
- **Selenium** (newspaper, nayiri): `pip install selenium`; Chrome/Chromium for browser automation.
- **HuggingFace** (culturax): `pip install datasets`; may need `huggingface-cli login` if dataset is gated.
- **DPLA**: API key — set `ingestion.dpla.api_key` (or `scraping.dpla.api_key`) in config or env `DPLA_API_KEY` (request: `POST https://api.dp.la/v2/api_key/YOUR_EMAIL`).

---

## 2. What's Ready to Test (no keys / no extra setup)

These stages work with only MongoDB + default config:

| Stage | What it does | Note |
|-------|----------------------|------|
| **wikipedia_wa** | Western Armenian Wikipedia → MongoDB | Streams dump or API; may download bz2 for resume |
| **wikipedia_ea** | Eastern Armenian Wikipedia → MongoDB | Same |
| **wikisource** | Wikisource Armenian → MongoDB | API |
| **archive_org** | Internet Archive search → MongoDB | No key; builds catalog in MongoDB |
| **gallica** | BnF Gallica SRU → MongoDB | No key; add `ingestion.gallica` (or `scraping.gallica`) in config if missing |
| **loc** | Library of Congress → MongoDB | No key; polite rate limiting |
| **gomidas** | Gomidas Institute PDFs → OCR → MongoDB | No key; scrapes resources page |
| **metadata_tagger** | Enriches document metadata in MongoDB | Runs over existing docs |
| **frequency_aggregator** | Builds word frequency list in MongoDB | Needs docs in DB |
| **cleaning** | Normalize/dedup/WA-filter in MongoDB | Needs docs in DB |
| **materialize_dialect_views** | Sets dialect_view on documents | Needs docs in DB |
| **summarize_unified_documents** | Corpus summary stats | Needs docs in DB |
| **validate_contract_alignment** | Validates corpus schema | Needs docs in DB |

---

## 3. Stages That Need Keys or Will Skip/Fail

| Stage | Requirement | If not set |
|-------|-------------|------------|
| **dpla** | DPLA API key in config or `DPLA_API_KEY` | **Fails** (run will error) — **skip for first test** |
| **hathitrust** | No key; uses catalog/seed list or HTRC bulk | Often **403** on public search; may only store catalog/metadata |
| **culturax** | HuggingFace; some datasets gated | May need `huggingface-cli login` or will fail on gated |
| **mechitarist** | `catalog_path` or API (partnership) | Exits cleanly, no error |
| **agbu** | `catalog_path` or API (partnership) | Exits cleanly, no error |
| **newspaper** | Selenium + Chrome | Fails if browser/driver missing |
| **nayiri** | Selenium | Fails if browser/driver missing |
| **ea_news** | None | Can run; some feeds may be down |
| **rss_news** | None | Can run |
| **english_sources** | None | Can run |
| **ocr_ingest** | Scans `paths.raw_dir` for files to OCR | No-op if directory empty |
| **mss_nkr** | None | Can run (downloads to disk) |
| **worldcat_searcher** | None | Catalog search only; doesn't insert into corpus |
| **import_anki_to_mongodb** | AnkiConnect → MongoDB | Fails if MongoDB unavailable |
| **export_corpus_overlap_fingerprints** | None | Runs over MongoDB |

---

## 4. Recommended First Test (minimal, no API keys)

Run only stages that don't require keys and that pull or process data:

```powershell
cd C:\Users\litni\armenian_projects\armenian-corpus-core

# Ensure MongoDB is running, then:
python -m ingestion.runner run --only wikipedia wikisource archive_org gallica loc gomidas
```

Then post-processing and extraction (they need documents in MongoDB):

```powershell
python -m ingestion.runner run --only metadata_tagger frequency_aggregator cleaning materialize_dialect_views summarize_unified_documents validate_contract_alignment
```

Or run scraping + post-processing in one go, but **skip** stages that require keys or often fail:

```powershell
python -m ingestion.runner run --skip dpla hathitrust culturax newspaper nayiri import_anki_to_mongodb worldcat_searcher mechitarist agbu
```

---

## 5. Verify Run

```powershell
# Pipeline status and last summary
python -m ingestion.runner status

# List all stages
python -m ingestion.runner list

# Dashboard (document counts by source)
python -m ingestion.runner dashboard --output data/logs/scraper_dashboard.html
# Open data/logs/scraper_dashboard.html in a browser
```

Check MongoDB:

```javascript
// In mongosh, connect to your DB (e.g. western_armenian_corpus)
use western_armenian_corpus
db.documents.countDocuments()
db.documents.aggregate([{ $group: { _id: "$source", count: { $sum: 1 } } }, { $sort: { count: -1 } }])
```

---

## 6. Optional: Add More Stages for a Full Test

- **DPLA**: Get API key, add to `config/settings.yaml` under `ingestion.dpla.api_key` (or `scraping.dpla.api_key`), then run `--only dpla` or include in full run.
- **CulturaX**: If dataset is gated, run `huggingface-cli login`, then enable and run `culturax`.
- **News**: Install Selenium and Chrome for `newspaper` and `nayiri`; then run those stages.
- **HathiTrust**: Use a seed list or HTRC bulk path in config if you have access; otherwise expect 403 on search.

---

## 7. Config Snippets

Ensure these exist in `config/settings.yaml` (your file already has most):

```yaml
database:
  use_mongodb: true
  mongodb_uri: "mongodb://localhost:27017/"
  mongodb_database: "western_armenian_corpus"

ingestion:   # or scraping (both work)
  wikipedia: { enabled: true, language: "hyw" }
  wikisource: { enabled: true }
  archive_org: { enabled: true }
  gallica: { enabled: true }   # add if missing
  loc: { enabled: true }
  gomidas: { enabled: true }
  # dpla: { enabled: true, api_key: "YOUR_KEY" }  # uncomment when you have a key
  metadata_tagger: { enabled: true }
  frequency_aggregator: { enabled: true }
  cleaning: { enabled: true }
  extraction: { enabled: true }
```

Pass config explicitly if not in default path:

```powershell
python -m ingestion.runner run --config config/settings.yaml --skip dpla ...
```

---

## Summary

1. **Start MongoDB**, install deps (`pip install -e ".[mongodb,rss,browser,huggingface]"`).
2. **First test:** `python -m ingestion.runner run --only wikipedia wikisource archive_org gallica loc gomidas` then `--only metadata_tagger frequency_aggregator cleaning materialize_dialect_views summarize_unified_documents validate_contract_alignment`.
3. **Or** full run with skips: `python -m ingestion.runner run --skip dpla hathitrust culturax newspaper nayiri import_anki_to_mongodb worldcat_searcher mechitarist agbu`.
4. **Verify:** `python -m ingestion.runner status` and `dashboard`; check `db.documents` in MongoDB.

For more detail: [DEVELOPMENT.md](development/DEVELOPMENT.md), [SCRAPING_RUNNER_AND_LOC.md](SCRAPING_RUNNER_AND_LOC.md), [SCRAPER_IMPLEMENTATION_STATUS.md](development/SCRAPER_IMPLEMENTATION_STATUS.md).
