"""AGBU Nubar Library (Paris) — stub for future partnership/export integration.

The AGBU Nubar Library holds 43,000+ printed books, 800,000+ archival documents, 1,400 periodicals.
Website: https://bnulibrary.org — no public REST API; access by appointment/partnership.
Partnership guide: docs/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md.
API/source summary: docs/DATA_SOURCES_API_REFERENCE.md.

When you obtain a bulk export or API access, set in config:
  scraping.agbu.catalog_path  or  scraping.agbu.export_path  — path to export file
  scraping.agbu.api_base       — optional API base URL
  scraping.agbu.api_key       — optional API key

Usage::
    python -m ingestion.acquisition.agbu run
    python -m ingestion.acquisition.agbu run --config config/settings.yaml
"""

from __future__ import annotations

import logging
from pathlib import Path

from hytools.ingestion._shared.helpers import open_mongodb_client, log_stage

logger = logging.getLogger(__name__)
_STAGE = "agbu"


def _load_catalog_from_path(export_path: Path) -> dict[str, dict]:
    """Load catalog from a bulk export file (JSON, JSONL, or CSV). Placeholder."""
    raise NotImplementedError(
        "AGBU Nubar catalog loader not implemented. "
        "When you have a bulk export from partnership, add parsing here and return dict keyed by item id."
    )


def run(config: dict) -> None:
    """Run AGBU Nubar ingestion if a catalog/export source is configured; otherwise log and exit."""
    config = config or {}
    scrape_cfg = config.get("scraping", {}).get("agbu", {}) or {}
    catalog_path = scrape_cfg.get("catalog_path") or scrape_cfg.get("export_path")
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
            logger.warning("AGBU Nubar: %s", e)
            return
    elif api_base and api_key:
        logger.warning(
            "AGBU Nubar API integration not yet implemented. "
            "Set scraping.agbu.catalog_path or export_path to a bulk export file when available."
        )
        return
    else:
        log_stage(
            logger,
            _STAGE,
            "no_source",
            message="AGBU Nubar Library requires partnership or bulk export. "
            "See docs/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md and docs/DATA_SOURCES_API_REFERENCE.md. "
            "Set scraping.agbu.catalog_path or export_path (or api_base + api_key) when you have access.",
        )
        return

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for AGBU Nubar ingestion")
        # TODO: ingest catalog items (download/fetch text, insert_or_skip)
        log_stage(logger, _STAGE, "run_complete", catalog_size=len(catalog))


if __name__ == "__main__":
    import argparse
    import sys
    import yaml

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="AGBU Nubar Library (Paris) scraper stub")
    parser.add_argument("run", nargs="?", default="run")
    parser.add_argument("--config", type=Path, default=Path("config/settings.yaml"))
    args = parser.parse_args()

    cfg = {}
    if args.config.exists():
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    run(cfg)
    sys.exit(0)
