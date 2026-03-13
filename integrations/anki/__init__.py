"""AnkiConnect client and configuration for Western Armenian flashcard pipelines.

Modules:
- client: AnkiConnect REST API client (localhost:8765, JSON-RPC v6)
- config: Deck names, note type models, field mappings, progression settings
- pull_pipeline: Full Anki export → local SQLite import pipeline
"""

from .client import AnkiConnect, AnkiConnectError
from .config import (
    ANKI_CONNECT_URL,
    ANKI_CONNECT_VERSION,
    SOURCE_DECK,
    TARGET_DECK,
)

__all__ = [
    "AnkiConnect",
    "AnkiConnectError",
    "ANKI_CONNECT_URL",
    "ANKI_CONNECT_VERSION",
    "SOURCE_DECK",
    "TARGET_DECK",
]
