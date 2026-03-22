"""Import Armenian etymology from Wiktextract/kaikki JSONL into MongoDB.

Usage:
    python -m linguistics.import_etymology_from_wiktextract --jsonl path/to/kaikki.jsonl [--config config/settings.yaml]
    python -m linguistics.import_etymology_from_wiktextract --jsonl path/to/kaikki.jsonl --max 10000

Requires database.mongodb_uri in config. Uses linguistics.lexicon.etymology_db to build
documents (lemma, source=wiktionary, confidence, etymology_text, relationships)
and upsert into the etymology collection.

Run: python -m linguistics.tools.import_etymology_from_wiktextract --jsonl path/to/kaikki.jsonl
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]  # linguistics/tools/import_*.py -> repo

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    default_config = _repo_root / "config" / "settings.yaml"
    parser = argparse.ArgumentParser(description="Import Armenian etymology from Wiktextract/kaikki JSONL into MongoDB")
    parser.add_argument("--jsonl", type=Path, required=True, help="Path to kaikki/wiktextract JSONL (e.g. kaikki.org-dictionary-Armenian.json)")
    parser.add_argument("--config", type=Path, default=default_config, help="Config YAML")
    parser.add_argument("--max", type=int, default=None, help="Max Armenian entries to process (default: all)")
    parser.add_argument("--confidence", type=float, default=0.85, help="Confidence for wiktionary-sourced entries")
    parser.add_argument("--log-every", type=int, default=5000, help="Log progress every N entries")
    args = parser.parse_args()

    if not args.jsonl.exists():
        logger.error("JSONL not found: %s", args.jsonl)
        return 1

    if not args.config.exists():
        logger.error("Config not found: %s", args.config)
        return 1

    try:
        import yaml
    except ImportError:
        logger.error("PyYAML required: pip install pyyaml")
        return 1

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if not cfg.get("database", {}).get("mongodb_uri"):
        logger.error("Config must have database.mongodb_uri")
        return 1

    from hytool.linguistics.lexicon.etymology_db import import_etymology_from_wiktextract
    from hytool.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(cfg) as client:
        if client is None:
            logger.error("MongoDB connection failed")
            return 1
        collection = client.etymology
        processed, upserted = import_etymology_from_wiktextract(
            args.jsonl,
            collection,
            max_entries=args.max,
            confidence=args.confidence,
            log_every=args.log_every,
        )

    logger.info("Done: processed=%d upserted=%d", processed, upserted)
    return 0


if __name__ == "__main__":
    sys.exit(main())

