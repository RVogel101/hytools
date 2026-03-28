"""Shared utilities for scraping modules.

Consolidates MongoDB helpers.
"""

from __future__ import annotations

import bz2
import json
import logging
import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List

from hytools.ingestion._shared.metadata import InternalLanguageBranch

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MongoDB helpers (kept compatible with prior public API)
# ---------------------------------------------------------------------------
try:
    from pymongo.errors import DuplicateKeyError  # type: ignore[reportMissingImports]
except ImportError:
    DuplicateKeyError = Exception  # type: ignore[misc,assignment]


def _get_mongodb_config(config: dict) -> tuple[str, str]:
    db_cfg = config.get("database", {})
    uri = db_cfg.get("mongodb_uri", "mongodb://localhost:27017/")
    db_name = db_cfg.get("mongodb_database", "western_armenian_corpus")
    return uri, db_name


@contextmanager
def open_mongodb_client(config: dict) -> Generator:
    try:
        from hytools.integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        logger.error("pymongo not installed. Run: pip install pymongo")
        yield None
        return

    uri, db_name = _get_mongodb_config(config)
    client = MongoDBCorpusClient(uri=uri, database_name=db_name)
    try:
        client.connect()
        logger.info("Connected to MongoDB: %s", db_name)
        yield client
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        yield None
    finally:
        client.close()

