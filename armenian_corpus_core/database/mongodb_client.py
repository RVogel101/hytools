"""MongoDB client for Western Armenian corpus storage.

Provides MongoDB connection management and corpus document operations.
This module can be used alongside or as a replacement for the SQLite system.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING  # type: ignore[reportMissingModuleSource]
    from pymongo.database import Database  # type: ignore[reportMissingModuleSource]
    from pymongo.collection import Collection  # type: ignore[reportMissingModuleSource]
    from pymongo.errors import ConnectionFailure, DuplicateKeyError  # type: ignore[reportMissingModuleSource]
    _PYMONGO_AVAILABLE = True
except ImportError:
    _PYMONGO_AVAILABLE = False
    MongoClient = None  # type: ignore
    ASCENDING = 1
    DESCENDING = -1
    Database = None  # type: ignore
    Collection = None  # type: ignore
    ConnectionFailure = Exception
    DuplicateKeyError = Exception

logger = logging.getLogger(__name__)


class MongoDBCorpusClient:
    """MongoDB client for Western Armenian corpus management."""

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017/",
        database_name: str = "western_armenian_corpus",
    ):
        """Initialize MongoDB connection.

        Args:
            uri: MongoDB connection URI
            database_name: Name of the database to use
        """
        self.uri = uri
        self.database_name = database_name
        self._client: Optional[Any] = None
        self._db: Optional[Any] = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def connect(self) -> None:
        """Establish MongoDB connection and verify it's alive."""
        if not _PYMONGO_AVAILABLE or MongoClient is None:
            raise RuntimeError("pymongo is not installed. Install with: pip install pymongo")
        try:
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            assert self._client is not None
            # Verify connection
            self._client.admin.command("ping")
            self._db = self._client[self.database_name]
            assert self._db is not None
            self._ensure_indexes()
            logger.info(f"Connected to MongoDB: {self.database_name}")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def close(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.debug("MongoDB connection closed")

    @property
    def db(self) -> Any:
        """Get database instance."""
        if not self._db:
            raise RuntimeError("Not connected to MongoDB. Call connect() first.")
        return self._db

    @property
    def documents(self) -> Any:
        """Get corpus documents collection."""
        return self.db["documents"]

    @property
    def metadata(self) -> Any:
        """Get metadata collection for pipeline tracking."""
        return self.db["metadata"]

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # Documents collection indexes
        self.documents.create_index([("source", ASCENDING)])
        self.documents.create_index([("title", ASCENDING)])
        self.documents.create_index([("metadata.date_scraped", DESCENDING)])
        self.documents.create_index([("processing.deduplicated", ASCENDING)])
        self.documents.create_index([("processing.filtered", ASCENDING)])
        self.documents.create_index([("content_hash", ASCENDING)], unique=True)

        # Metadata collection indexes
        self.metadata.create_index([("stage", ASCENDING)])
        self.metadata.create_index([("timestamp", DESCENDING)])

        logger.debug("MongoDB indexes created")

    # ── Document Operations ─────────────────────────────────────────────────

    def insert_document(
        self,
        source: str,
        title: str,
        text: str,
        url: Optional[str] = None,
        author: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Insert a corpus document.

        Args:
            source: Source identifier (e.g., "wikipedia", "wikisource")
            title: Document title
            text: Full text content
            url: Original URL if applicable
            author: Author name if known
            metadata: Additional custom metadata

        Returns:
            Inserted document ID (as string)

        Raises:
            DuplicateKeyError: If document with same content_hash exists
        """
        import hashlib

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        doc = {
            "source": source,
            "title": title,
            "text": text,
            "content_hash": content_hash,
            "metadata": {
                "url": url,
                "author": author,
                "date_scraped": datetime.utcnow(),
                "word_count": len(text.split()),
                "char_count": len(text),
                **(metadata or {}),
            },
            "processing": {
                "normalized": False,
                "deduplicated": False,
                "filtered": False,
                "dialect_classified": False,
            },
        }

        try:
            result = self.documents.insert_one(doc)
            logger.debug(f"Inserted document: {title} (ID: {result.inserted_id})")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Duplicate document detected (hash: {content_hash[:16]}...)")
            raise

    def get_document(self, doc_id: str) -> Optional[dict]:
        """Retrieve a document by ID.

        Args:
            doc_id: MongoDB ObjectId as string

        Returns:
            Document dict or None if not found
        """
        from bson import ObjectId  # type: ignore[reportMissingModuleSource]

        try:
            return self.documents.find_one({"_id": ObjectId(doc_id)})
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {e}")
            return None

    def find_documents(
        self,
        source: Optional[str] = None,
        processed: Optional[bool] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query documents with filters.

        Args:
            source: Filter by source (e.g., "wikipedia")
            processed: Filter by processing status (fully processed or not)
            limit: Maximum number of documents to return

        Returns:
            List of matching documents
        """
        query = {}
        if source:
            query["source"] = source
        if processed is not None:
            query["processing.filtered"] = processed

        return list(self.documents.find(query).limit(limit))

    def update_processing_status(
        self,
        doc_id: str,
        normalized: bool = False,
        deduplicated: bool = False,
        filtered: bool = False,
        dialect_classified: bool = False,
    ) -> bool:
        """Update document processing flags.

        Args:
            doc_id: MongoDB ObjectId as string
            normalized: Text has been normalized
            deduplicated: Document passed deduplication
            filtered: Document passed Western Armenian filter
            dialect_classified: Dialect has been determined

        Returns:
            True if updated, False if document not found
        """
        from bson import ObjectId  # type: ignore[reportMissingModuleSource]

        result = self.documents.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "processing.normalized": normalized,
                    "processing.deduplicated": deduplicated,
                    "processing.filtered": filtered,
                    "processing.dialect_classified": dialect_classified,
                }
            },
        )

        return result.matched_count > 0

    def count_documents(self, source: Optional[str] = None) -> int:
        """Count documents in corpus.

        Args:
            source: Filter by source, or None for all

        Returns:
            Document count
        """
        query = {"source": source} if source else {}
        return self.documents.count_documents(query)

    # ── Pipeline Metadata ───────────────────────────────────────────────────

    def log_pipeline_run(self, stage: str, status: str, details: Optional[dict] = None) -> None:
        """Log a pipeline stage execution.

        Args:
            stage: Stage name (e.g., "scraping", "cleaning")
            status: Status (e.g., "ok", "error")
            details: Additional run details
        """
        entry = {
            "stage": stage,
            "status": status,
            "timestamp": datetime.utcnow(),
            "details": details or {},
        }
        self.metadata.insert_one(entry)
        logger.info(f"Logged pipeline run: {stage} ({status})")

    def get_latest_run(self, stage: str) -> Optional[dict]:
        """Get most recent pipeline run for a stage.

        Args:
            stage: Stage name

        Returns:
            Most recent run entry or None
        """
        return self.metadata.find_one({"stage": stage}, sort=[("timestamp", DESCENDING)])

    # ── Bulk Operations ─────────────────────────────────────────────────────

    def bulk_insert_from_files(
        self, 
        source: str, 
        file_paths: list[Path],
        metadata_extractor: Optional[Callable[[Path], dict]] = None
    ) -> dict:
        """Bulk insert documents from text files.

        Args:
            source: Source identifier
            file_paths: List of .txt file paths
            metadata_extractor: Optional function(path) -> dict to extract metadata

        Returns:
            Dictionary with {"inserted": int, "duplicates": int, "errors": int}
        """
        stats = {"inserted": 0, "duplicates": 0, "errors": 0}

        for path in file_paths:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                title = path.stem

                # Extract metadata using custom extractor or default
                if metadata_extractor:
                    extra_metadata = metadata_extractor(path)
                else:
                    extra_metadata = {}

                self.insert_document(
                    source=source,
                    title=title,
                    text=text,
                    metadata={
                        "file_path": str(path),
                        **extra_metadata
                    },
                )
                stats["inserted"] += 1

            except DuplicateKeyError:
                stats["duplicates"] += 1
            except Exception as e:
                logger.error(f"Error inserting {path}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Bulk insert complete: {stats['inserted']} inserted, "
            f"{stats['duplicates']} duplicates, {stats['errors']} errors"
        )
        return stats


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    with MongoDBCorpusClient() as client:
        # Test connection
        count = client.count_documents()
        print(f"Current document count: {count}")

        # Test insert
        doc_id = client.insert_document(
            source="test",
            title="Test Document",
            text="Այս թեստի փաստաթուղթ է։",
            metadata={"test": True},
        )
        print(f"Inserted test document: {doc_id}")

        # Test query
        doc = client.get_document(doc_id)
        if doc is not None:
            print(f"Retrieved: {doc['title']}")

        # Cleanup
        if doc is not None:
            client.documents.delete_one({"_id": doc["_id"]})
        print("Test document removed")
