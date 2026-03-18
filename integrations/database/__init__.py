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

from .adapters import (
    NewspaperDatabaseAdapter,
    NayiriDatabaseAdapter,
    ArchiveOrgDatabaseAdapter,
    GenericDatabaseAdapter,
)
from .telemetry import ProcessTelemetry
from .migrator import DataMigrator
from .mongodb_client import MongoDBCorpusClient

__all__ = [
    "NewspaperDatabaseAdapter",
    "NayiriDatabaseAdapter",
    "ArchiveOrgDatabaseAdapter",
    "GenericDatabaseAdapter",
    "ProcessTelemetry",
    "DataMigrator",
    "MongoDBCorpusClient",
]

