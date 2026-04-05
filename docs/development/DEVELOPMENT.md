# Development Workflow

This is the canonical workflow and command reference for hytools.

- Primary onboarding: `docs/QUICK_START_PHASE1.md`
- Current active backlog: `docs/development/CURRENT_BACKLOG.md`
- Broader roadmap and ideas: `docs/development/FUTURE_IMPROVEMENTS.md`

## Canonical stage runner

The authoritative CLI for the ingestion pipeline is `hytools.ingestion.runner`.

### Core commands

```bash
python -m hytools.ingestion.runner run --config config/settings.yaml
python -m hytools.ingestion.runner status
python -m hytools.ingestion.runner list
python -m hytools.ingestion.runner doctor --config config/settings.yaml
python -m hytools.ingestion.runner dashboard --config config/settings.yaml --output data/logs/scraper_dashboard.html
```

`doctor` validates the active config, surfaces missing paths and placeholder credentials, checks optional dependencies, and warns when stages are still depending on implicit transition defaults.

### Stage groups

```bash
python -m hytools.ingestion.runner run --config config/settings.yaml --group scraping
python -m hytools.ingestion.runner run --config config/settings.yaml --group extraction
python -m hytools.ingestion.runner run --config config/settings.yaml --group postprocessing
```

### Stage selection

```bash
python -m hytools.ingestion.runner run --config config/settings.yaml --only news
python -m hytools.ingestion.runner run --config config/settings.yaml --only wikipedia wikisource archive_org
python -m hytools.ingestion.runner run --config config/settings.yaml --skip nayiri
```

### Background run

```bash
python -m hytools.ingestion.runner run --config config/settings.yaml --background
python -m hytools.ingestion.runner status
```

### Release build

```bash
python -m hytools.ingestion.runner release --config config/settings.yaml --output data/releases/latest
```

The release command builds deterministic train, validation, and test splits together with a manifest, checksum file, and dataset card.

## Wrapper script

`scripts/run_pipeline.py` is the repo-level wrapper for multi-stage runs that span ingestion plus OCR and cleaning.

```bash
python scripts/run_pipeline.py --stage scrape --config config/settings.yaml
python scripts/run_pipeline.py --stage scrape --config config/settings.yaml --only-runner-stage archive_org loc
python scripts/run_pipeline.py --stage ocr --config config/settings.yaml
python scripts/run_pipeline.py --stage ocr --config config/settings.yaml --pdf data/raw/sample.pdf
python scripts/run_pipeline.py --stage clean --config config/settings.yaml
python scripts/run_pipeline.py --stage ingest --config config/settings.yaml
python scripts/run_pipeline.py --stage all --config config/settings.yaml --skip-runner-stage metadata_tagger
python scripts/run_pipeline.py --stage all --config config/settings.yaml --dry-run
python scripts/run_pipeline.py --stage all --config config/settings.yaml
```

Current wrapper limitations:

- No single-source shorthand yet; use `--only-runner-stage` / `--skip-runner-stage` with canonical runner stage names
- The ingestion runner remains the canonical command surface for stage-level operations

## Tests

```bash
python -m pytest tests/ -v
python -m pytest tests/test_scheduler.py -q --tb=line
```

## Code quality

```bash
black hytools scripts tests
isort hytools scripts tests
mypy hytools
```

## Troubleshooting

- If a command example disagrees with source, defer to `hytools/ingestion/runner.py`.
- If a run depends on local settings, verify `config/settings.yaml` exists and the referenced paths resolve.
- If MongoDB-backed stages fail, confirm the `database.*` settings in `config/settings.yaml` and that MongoDB is reachable.
