"""Mechitarist Library (San Lazzaro, Venice) — stub for future catalog/API integration.

The Mechitarist Congregation holds 1,500+ Armenian printed works (17th–20th century).
Online catalog: https://catalog.mechitar.org/ (no public REST API).
Permission template: docs/MECHITARIST_PERMISSION_REQUEST.md.
API/source summary: docs/DATA_SOURCES_API_REFERENCE.md.

When you obtain a bulk export or API access, set in config:
  scraping.mechitarist.catalog_path  — path to JSON/JSONL/CSV export
  scraping.mechitarist.api_base      — optional API base URL
  scraping.mechitarist.api_key       — optional API key

Usage::
    python -m ingestion.acquisition.mechitarist run
    python -m ingestion.acquisition.mechitarist run --config config/settings.yaml
"""

from __future__ import annotations

import logging
from pathlib import Path

from hytool.ingestion._shared.helpers import open_mongodb_client, log_stage

logger = logging.getLogger(__name__)
_STAGE = "mechitarist"


def _load_catalog_from_path(catalog_path: Path) -> dict[str, dict]:
    """Load catalog from a bulk export file (JSON, JSONL, or CSV). Placeholder."""
    raise NotImplementedError(
        "Mechitarist catalog loader not implemented. "
        "When you have a bulk export, add parsing here and return dict keyed by item id."
    )


def run(config: dict) -> None:
    """Run Mechitarist ingestion if a catalog source is configured; otherwise log and exit."""
    config = config or {}
    scrape_cfg = config.get("scraping", {}).get("mechitarist", {}) or {}
    catalog_path = scrape_cfg.get("catalog_path")
    api_base = scrape_cfg.get("api_base")
    api_key = scrape_cfg.get("api_key")

    if catalog_path:
        path = Path(catalog_path)
        if not path.exists():
            log_stage(logger, _STAGE, "catalog_not_found", path=str(path))
            return
        try:
            catalog = _load_catalog_from_path(path)
        except NotImplementedError as e:
            logger.warning("Mechitarist: %s", e)
            return
    elif api_base and api_key:
        logger.warning(
            "Mechitarist API integration not yet implemented. "
            "Set scraping.mechitarist.catalog_path to a bulk export file when available."
        )
        return
    else:
        log_stage(
            logger,
            _STAGE,
            "no_source",
            message="Mechitarist requires permission or bulk export. "
            "See docs/MECHITARIST_PERMISSION_REQUEST.md and docs/DATA_SOURCES_API_REFERENCE.md. "
            "Set scraping.mechitarist.catalog_path (or api_base + api_key) when you have access.",
        )
        return

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for Mechitarist ingestion")
        # TODO: ingest catalog items (download/fetch text, insert_or_skip)
        log_stage(logger, _STAGE, "run_complete", catalog_size=len(catalog))


if __name__ == "__main__":
    import argparse
    import sys
    import yaml

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Mechitarist Library (Venice) scraper stub")
    parser.add_argument("run", nargs="?", default="run")
    parser.add_argument("--config", type=Path, default=Path("config/settings.yaml"))
    args = parser.parse_args()

    cfg = {}
    if args.config.exists():
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    run(cfg)
    sys.exit(0)

