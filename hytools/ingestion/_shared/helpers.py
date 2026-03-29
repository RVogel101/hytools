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


# ---------------------------------------------------------------------------
# Backwards-compatible re-exports for legacy consumers
# Some modules import WA/EA marker getters and constants from
# `hytools.ingestion._shared.helpers`; those functions now live in
# `hytools.linguistics.dialect.branch_dialect_classifier`. Provide
# lightweight re-exports and reasonable defaults to avoid ImportError
# when older import paths are used.
# ---------------------------------------------------------------------------
try:
    from hytools.linguistics.dialect.branch_dialect_classifier import (
        get_classical_markers,
        get_lexical_markers,
        get_wa_vocabulary_markers,
        get_eastern_markers,
        get_wa_standalone_patterns,
        get_wa_suffix_patterns,
        get_ea_regex_patterns,
        get_word_internal_e_long_re,
        get_word_ending_ay_re,
        get_word_ending_oy_re,
        get_wa_authors,
        get_wa_publication_cities,
        get_wa_score_threshold,
        get_armenian_punctuation,
    )

    # Provide constants expected by older callers
    _ARMENIAN_PUNCT = get_armenian_punctuation()
    _WA_PUBLICATION_CITIES = list(get_wa_publication_cities())
    _EAST_ARMENIAN_AUTHORS = []

    import re as _re

    _REFORMED_SUFFIX_RE = _re.compile(r"\u0578\u0582\u0569\u0575\u0578\u0582\u0576")
    _CLASSICAL_SUFFIX_RE = _re.compile(r"\u0578\u0582\u0569\u056B\u0582\u0576")

    # Minimal placeholders for word-boundary helpers (previously provided)
    _ARM_WB_L = r""
    _ARM_WB_R = r""
    _ARM_PRECEDED = r""
except Exception:  # pragma: no cover - best-effort compatibility shim
    pass

