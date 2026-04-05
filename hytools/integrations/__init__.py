"""External system integrations: corpus/card databases only.

This package groups adapters for external systems:
- database: Corpus SQLite DB, card DB, adapters, migrator, telemetry
"""

import importlib as _importlib

__all__ = ["database"]


def __getattr__(name: str):
    if name == "database":
        return _importlib.import_module(".database", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
