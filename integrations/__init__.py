"""External system integrations: AnkiConnect and corpus/card databases.

This package groups adapters for external systems:
- anki: AnkiConnect client and pull pipeline
- database: Corpus SQLite DB, card DB, adapters, migrator, telemetry
"""

from . import anki
from . import database

__all__ = ["anki", "database"]
