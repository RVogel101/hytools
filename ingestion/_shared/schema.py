"""Schema contract for Anki-backed flashcard documents stored in MongoDB.

This module defines the canonical set of fields that the Anki importer
must write and the rest of the system expects to exist.

Keeping a single source of truth avoids duplicated schema lists across
importers and tests.
"""

from __future__ import annotations

from typing import Final, List

# The exact set of fields that must exist on every card document.
# These are used by the importer and by schema validation tests.
CARD_SCHEMA_KEYS: Final[List[str]] = [
    "anki_note_id",
    "deck_name",
    "sub_deck_name",
    "anki_deck_name",
    "word",
    "translation",
    "pos",
    "card_type",
    "frequency_rank",
    "syllable_count",
    "tags",
    "model_name",
    "deck_id",
    "guid",
    "fields",
    "flags",
    "data",
    "usn",
    "mod",
    "created",
    "cards",
    "metadata_json",
    "morphology_json",
    "custom_level",
]

# Minimal subset that must be non-blank for a card to be valid.
REQUIRED_CARD_FIELDS: Final[List[str]] = [
    "anki_note_id",
    "word",
    "translation",
]
