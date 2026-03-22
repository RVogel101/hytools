"""Upload PDF/image files to MongoDB GridFS for centralized backup.

Usage::

    python -m ingestion.tools.upload_sources_to_gridfs --path data/raw/mss_nkr --source mss_nkr
    python -m ingestion.tools.upload_sources_to_gridfs --path data/raw/gomidas --source gomidas --config config/settings.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    default_config = repo_root / "config" / "settings.yaml"

    parser = argparse.ArgumentParser(description="Upload source PDFs/images to GridFS")
    parser.add_argument("--path", type=Path, required=True, help="Directory with PDFs/images")
    parser.add_argument("--source", default="upload", help="Source identifier for metadata")
    parser.add_argument("--config", type=Path, default=default_config)
    args = parser.parse_args()

    if not args.path.exists():
        logger.error("Path not found: %s", args.path)
        return 1

    cfg = {}
    if args.config.exists():
        import yaml
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    try:
        from hytools.integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        logger.error("pymongo required. pip install pymongo")
        return 1

    uri = cfg.get("database", {}).get("mongodb_uri", "mongodb://localhost:27017/")
    db = cfg.get("database", {}).get("mongodb_database", "western_armenian_corpus")

    files = []
    for ext in _SUPPORTED:
        files.extend(args.path.rglob(f"*{ext}"))

    if not files:
        logger.warning("No PDF/image files in %s", args.path)
        return 0

    uploaded = 0
    with MongoDBCorpusClient(uri=uri, database_name=db) as client:
        for f in files:
            try:
                client.upload_source_binary(f, source=args.source, metadata={"original_path": str(f)})
                uploaded += 1
                logger.info("Uploaded: %s", f.name)
            except Exception as e:
                logger.warning("Failed %s: %s", f.name, e)

    logger.info("Uploaded %d/%d files to GridFS", uploaded, len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
