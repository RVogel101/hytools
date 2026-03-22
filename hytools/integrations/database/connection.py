"""Legacy database connection interface (placeholder).

This module exists purely to satisfy imports from other modules that still
reference `integrations.database.connection`. It no longer provides a working
SQLite implementation; MongoDB is the supported storage backend.

If you need SQLite access for legacy tooling, consider restoring a real
implementation or using a separate migration script.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class DatabaseConnection:
    """Dummy connection object used only to satisfy legacy imports."""

    def __init__(self, *args: Any, **kwargs: Any):
        raise RuntimeError(
            "SQLite-based DatabaseConnection is not supported. "
            "Use MongoDB via integrations.database.mongodb_client instead."
        )


def connect(*args: Any, **kwargs: Any) -> DatabaseConnection:
    """Placeholder connect function."""
    return DatabaseConnection(*args, **kwargs)
