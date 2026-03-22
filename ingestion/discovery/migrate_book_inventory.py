"""One-time migration: load book inventory and author profiles from JSONL, save to MongoDB.

Usage:
    python -m ingestion.discovery.migrate_book_inventory --config config/settings.yaml

Requires config with database.mongodb_uri. Reads from data/book_inventory.jsonl and
data/author_profiles.jsonl if they exist; writes to MongoDB.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ingestion/discovery/migrate_book_inventory.py -> discovery -> ingestion -> repo
_repo_root = Path(__file__).resolve().parents[3]

from hytool.ingestion.discovery.book_inventory import BookInventoryManager
from hytool.ingestion.discovery.author_research import AuthorProfileManager

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    default_config = _repo_root / "config" / "settings.yaml"
    default_inventory = _repo_root / "data" / "book_inventory.jsonl"
    default_profiles = _repo_root / "data" / "author_profiles.jsonl"

    parser = argparse.ArgumentParser(description="Migrate book inventory and author profiles to MongoDB")
    parser.add_argument("--config", type=Path, default=default_config, help="Config YAML")
    parser.add_argument("--inventory", type=Path, default=default_inventory, help="Book inventory JSONL")
    parser.add_argument("--profiles", type=Path, default=default_profiles, help="Author profiles JSONL")
    args = parser.parse_args()

    if not args.config.exists():
        logger.error("Config not found: %s", args.config)
        return 1

    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if not cfg.get("database", {}).get("mongodb_uri"):
        logger.error("Config must have database.mongodb_uri")
        return 1

    migrated = 0

    if args.inventory.exists():
        logger.info("Migrating book inventory from %s...", args.inventory)
        loader = BookInventoryManager(inventory_file=str(args.inventory), config={})
        saver = BookInventoryManager(inventory_file=str(args.inventory), config=cfg)
        saver.books = loader.books
        count = saver.save_inventory()
        if isinstance(count, int):
            logger.info("  -> Migrated %d books to MongoDB", count)
            migrated += 1
    else:
        logger.info("No book inventory file at %s; skipping", args.inventory)

    if args.profiles.exists():
        logger.info("Migrating author profiles from %s...", args.profiles)
        loader = AuthorProfileManager(profiles_file=str(args.profiles), config={})
        saver = AuthorProfileManager(profiles_file=str(args.profiles), config=cfg)
        saver.profiles = loader.profiles
        count = saver.save_profiles()
        if isinstance(count, int):
            logger.info("  -> Migrated %d author profiles to MongoDB", count)
            migrated += 1
    else:
        logger.info("No author profiles file at %s; skipping", args.profiles)

    if migrated == 0 and not args.inventory.exists() and not args.profiles.exists():
        logger.warning("No JSONL files found; nothing to migrate")
        return 0

    logger.info("Migration complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

