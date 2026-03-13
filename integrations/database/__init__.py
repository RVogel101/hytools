"""Database layer for Armenian corpus and flashcard data.

Modules:
- corpus_schema: Corpus ingestion schema (16 tables: newspapers, Nayiri,
  Archive.org, Wikipedia, CulturaX, HathiTrust, LoC, Wikisource, dedup,
  migration, telemetry, metrics, quality, training allocations)
- connection: CorpusDatabase context-manager with CRUD helpers
- card_schema: Flashcard / spaced-repetition schema (anki_cards,
  card_enrichment, sentences, users, card_reviews, vocabulary)
- card_database: CardDatabase class with upsert, review, vocabulary cache
- adapters: Database adapters for direct SQLite writes from scrapers
- telemetry: Process telemetry and comprehensive logging system
- migrator: DataMigrator for JSONL-to-SQLite checkpoint migration
- mongodb_client: MongoDBCorpusClient (optional — requires pymongo)
"""

from .connection import CorpusDatabase
from .card_database import CardDatabase
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
    "CorpusDatabase",
    "CardDatabase",
    "NewspaperDatabaseAdapter",
    "NayiriDatabaseAdapter",
    "ArchiveOrgDatabaseAdapter",
    "GenericDatabaseAdapter",
    "ProcessTelemetry",
    "DataMigrator",
    "MongoDBCorpusClient",
]

