"""Database integration layer for the corpus and flashcard data.

This package provides a MongoDB-native client for all persistent storage.
The legacy SQLite-based adapters and schema implementations are removed.

Modules:
- corpus_schema: Corpus ingestion schema definitions (storage-agnostic)
- adapters: Database adapters for direct writes from scrapers
- telemetry: Process telemetry and logging system
- migrator: Migration helpers (JSONL -> MongoDB, etc.)
- mongodb_client: MongoDBCorpusClient (requires pymongo)
"""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "NewspaperDatabaseAdapter": ("adapters", "NewspaperDatabaseAdapter"),
    "NayiriDatabaseAdapter": ("adapters", "NayiriDatabaseAdapter"),
    "ArchiveOrgDatabaseAdapter": ("adapters", "ArchiveOrgDatabaseAdapter"),
    "GenericDatabaseAdapter": ("adapters", "GenericDatabaseAdapter"),
    "ProcessTelemetry": ("telemetry", "ProcessTelemetry"),
    "DataMigrator": ("migrator", "DataMigrator"),
    "MongoDBCorpusClient": ("mongodb_client", "MongoDBCorpusClient"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__

