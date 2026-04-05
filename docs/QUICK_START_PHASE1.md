# Quick Start: hytools Pipeline

This is the canonical onboarding document for the hytools repository.

- Canonical workflow and command reference: `docs/development/DEVELOPMENT.md`
- Current active backlog: `docs/development/CURRENT_BACKLOG.md`
- Broader roadmap: `docs/development/FUTURE_IMPROVEMENTS.md`

## Prerequisites

- Python 3.10+
- MongoDB running locally on `mongodb://localhost:27017/`
- A runtime config file at `config/settings.yaml`

Start from `config/settings.example.yaml` if you need to rebuild your local config.

## Install

```bash
pip install -e ".[dev]"
```

## First checks

```bash
python -m hytools.ingestion.runner list
python -m hytools.ingestion.runner status
python -m hytools.ingestion.runner doctor --config config/settings.yaml
```

## Canonical first run

```bash
python -m hytools.ingestion.runner run --config config/settings.yaml
```

## Common variants

```bash
python -m hytools.ingestion.runner run --config config/settings.yaml --group scraping
python -m hytools.ingestion.runner run --config config/settings.yaml --group extraction
python -m hytools.ingestion.runner run --config config/settings.yaml --group postprocessing
python -m hytools.ingestion.runner run --config config/settings.yaml --only news
python -m hytools.ingestion.runner run --config config/settings.yaml --skip nayiri
python -m hytools.ingestion.runner dashboard --config config/settings.yaml --output data/logs/scraper_dashboard.html
python -m hytools.ingestion.runner release --config config/settings.yaml --output data/releases/latest
```

The `doctor` command reports missing paths, placeholder secrets, optional dependency gaps, and stages that still rely on transitional implicit defaults.

## Wrapper script

Use the wrapper only when you want one command that spans scrape, OCR, cleaning, and ingest:

```bash
python scripts/run_pipeline.py --stage all --config config/settings.yaml
```

The stage runner above remains the canonical command surface for ingestion stages.

## Verification

```bash
python -m pytest tests/ -v
```
