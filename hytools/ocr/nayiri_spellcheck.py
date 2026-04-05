"""Nayiri-backed spell-check for OCR post-processing.

Loads the full word-form inventory from the MongoDB ``nayiri_entries``
collection into an in-memory set for O(1) look-ups, then exposes helpers
used by the confusion-pair corrector in ``postprocessor.py``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"

# Module-level singleton – populated once by ``load_nayiri_wordset()``.
_wordset: Optional[set[str]] = None

# Unicode range for Armenian characters (U+0530–U+058F).
_ARMENIAN_RE = re.compile(r"[\u0530-\u058F]")


def _is_armenian_token(token: str) -> bool:
    """Return *True* if *token* contains at least one Armenian character."""
    return bool(_ARMENIAN_RE.search(token))


def load_nayiri_wordset(config: Optional[dict] = None) -> set[str]:
    """Return a set of every word-form string in the Nayiri lexicon.

    The set is cached at module level so repeated calls are free.  If MongoDB
    is unreachable or the collection is empty the function returns an empty set
    and logs a warning (never raises).

    Parameters
    ----------
    config:
        A dict with ``database.mongodb_uri`` and ``database.mongodb_database``
        keys.  When *None* the project ``config/settings.yaml`` is read.
    """
    global _wordset
    if _wordset is not None:
        return _wordset

    if config is None:
        try:
            config = yaml.safe_load(_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read settings.yaml: %s", exc)
            _wordset = set()
            return _wordset

    try:
        from hytools.ingestion._shared.helpers import open_mongodb_client

        with open_mongodb_client(config) as client:
            if client is None:
                logger.warning("MongoDB unavailable – Nayiri spell-check disabled")
                _wordset = set()
                return _wordset

            coll = client.db.get_collection("nayiri_entries")
            cursor = coll.find({}, {"word_forms": 1, "headword": 1, "_id": 0})
            words: set[str] = set()
            for doc in cursor:
                hw = doc.get("headword")
                if hw:
                    words.add(hw)
                for form in doc.get("word_forms") or []:
                    if isinstance(form, str):
                        words.add(form)

            _wordset = words
            logger.info("Loaded %d Nayiri word-forms for spell-check", len(_wordset))
            return _wordset

    except Exception as exc:
        logger.warning("Failed to load Nayiri wordset: %s", exc)
        _wordset = set()
        return _wordset


def reset_wordset() -> None:
    """Clear the cached wordset (useful for testing)."""
    global _wordset
    _wordset = None


def is_valid_word(token: str, wordset: set[str]) -> bool:
    """Return *True* if *token* (or its lower-cased form) is in the wordset."""
    return token in wordset or token.lower() in wordset


def check_token(token: str, wordset: set[str]) -> bool:
    """Return *True* if the Armenian *token* passes spell-check.

    Non-Armenian tokens are always accepted (they are not checked).
    """
    if not _is_armenian_token(token):
        return True
    return is_valid_word(token, wordset)
