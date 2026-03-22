"""External system integrations: corpus/card databases only.

This package groups adapters for external systems:
- database: Corpus SQLite DB, card DB, adapters, migrator, telemetry
"""

from . import database

__all__ = ["database"]
