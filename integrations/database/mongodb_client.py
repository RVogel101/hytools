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
    from gridfs import GridFS  # type: ignore[reportMissingModuleSource]
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
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            logger.debug("MongoDB connection closed")

    @property
    def db(self) -> Any:
        """Get database instance."""
        if self._db is None:
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

    @property
    def catalogs(self) -> Any:
        """Get catalogs collection for source item metadata (LOC, HathiTrust, etc.)."""
        return self.db["catalogs"]

    @property
    def book_inventory(self) -> Any:
        """Get book inventory collection."""
        return self.db["book_inventory"]

    @property
    def author_profiles(self) -> Any:
        """Get author profiles collection."""
        return self.db["author_profiles"]

    @property
    def author_chronology(self) -> Any:
        """Chronology events (year, author, event, place, details). Replaces CSV export."""
        return self.db["author_chronology"]

    @property
    def author_bibliography(self) -> Any:
        """Bibliography entries (author, author_id, title, year, type, etc.). Replaces JSONL export."""
        return self.db["author_bibliography"]

    @property
    def author_research_summary(self) -> Any:
        """Single-doc collection for author research summary report (generated, stats)."""
        return self.db["author_research_summary"]

    @property
    def author_timeline(self) -> Any:
        """Single-doc collection for full author timeline (timeline + metadata)."""
        return self.db["author_timeline"]

    @property
    def author_period_analysis(self) -> Any:
        """Single-doc collection for period analysis (period -> authors)."""
        return self.db["author_period_analysis"]

    @property
    def author_generation_report(self) -> Any:
        """Single-doc collection for generation report."""
        return self.db["author_generation_report"]

    @property
    def coverage_gaps(self) -> Any:
        """Single-doc collection for coverage gaps report (summary + gaps list)."""
        return self.db["coverage_gaps"]

    @property
    def acquisition_priorities(self) -> Any:
        """Single-doc collection for acquisition priorities (priority_filter + rows)."""
        return self.db["acquisition_priorities"]

    @property
    def augmentation_checkpoint(self) -> Any:
        """Get augmentation checkpoint collection (task_uid -> done)."""
        return self.db["augmentation_checkpoint"]

    @property
    def augmentation_metrics(self) -> Any:
        """Get augmentation metrics collection (batch reports, metric cards)."""
        return self.db["augmentation_metrics"]

    @property
    def etymology(self) -> Any:
        """Get etymology / loanword_origin collection (lemma → source, confidence, etymology text)."""
        return self.db["etymology"]

    @property
    def source_binaries_fs(self) -> Any:
        """Get GridFS bucket for source documents (PDFs, images)."""
        if GridFS is None:
            raise RuntimeError("gridfs not available. Install pymongo with gridfs support.")
        return GridFS(self.db, collection="source_binaries")

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # Documents collection indexes
        self.documents.create_index([("source", ASCENDING)])
        self.documents.create_index([("title", ASCENDING)])
        self.documents.create_index([("metadata.date_scraped", DESCENDING)])
        self.documents.create_index([("processing.deduplicated", ASCENDING)])
        self.documents.create_index([("processing.filtered", ASCENDING)])
        self.documents.create_index([("content_hash", ASCENDING)], unique=True)
        self.documents.create_index([("normalized_content_hash", ASCENDING)])

        # Metadata collection indexes
        self.metadata.create_index([("stage", ASCENDING)])
        self.metadata.create_index([("timestamp", DESCENDING)])

        # Catalogs collection (source item metadata for LOC, HathiTrust, etc.)
        self.catalogs.create_index([("source", ASCENDING), ("item_id", ASCENDING)], unique=True)
        self.catalogs.create_index([("source", ASCENDING)])

        # Book inventory
        self.book_inventory.create_index([("title", ASCENDING)])
        self.book_inventory.create_index([("coverage_status", ASCENDING)])
        self.book_inventory.create_index([("authors.name", ASCENDING)])

        # Author profiles
        self.author_profiles.create_index([("author_id", ASCENDING)], unique=True)
        self.author_profiles.create_index([("primary_name", ASCENDING)])

        # Author research exports (no local CSV/JSONL)
        self.author_chronology.create_index([("year", ASCENDING)])
        self.author_chronology.create_index([("author", ASCENDING)])
        self.author_bibliography.create_index([("author_id", ASCENDING)])
        self.author_bibliography.create_index([("author", ASCENDING)])
        self.author_research_summary.create_index([("generated", DESCENDING)])

        # Author timeline / period / generation (no local file output)
        self.author_timeline.create_index([("metadata.generated", DESCENDING)])
        self.coverage_gaps.create_index([("generated", DESCENDING)])
        self.acquisition_priorities.create_index([("generated", DESCENDING)])

        # Augmentation checkpoint
        self.augmentation_checkpoint.create_index([("task_uid", ASCENDING)], unique=True)

        # Etymology / loanword_origin (Phase 1: Wiktextract import)
        self.etymology.create_index([("lemma", ASCENDING)], unique=True)
        self.etymology.create_index([("source", ASCENDING)])

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
        import re
        import unicodedata

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        normalized = unicodedata.normalize("NFKC", text)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized_content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        doc = {
            "source": source,
            "title": title,
            "text": text,
            "content_hash": content_hash,
            "normalized_content_hash": normalized_content_hash,
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

    # ── Catalog Operations ───────────────────────────────────────────────────

    def upsert_catalog_items(self, source: str, catalog: dict[str, dict]) -> int:
        """Upsert catalog items to MongoDB. Each item has item_id as key.

        Args:
            source: Source identifier (e.g., "loc", "hathitrust", "gallica")
            catalog: Dict of item_id -> {title, url, downloaded, ...}

        Returns:
            Number of items upserted
        """
        from datetime import datetime
        count = 0
        for item_id, item in catalog.items():
            doc = {
                "source": source,
                "item_id": item_id,
                **{k: v for k, v in item.items() if k != "source"},
                "updated_at": datetime.utcnow(),
            }
            self.catalogs.update_one(
                {"source": source, "item_id": item_id},
                {"$set": doc},
                upsert=True,
            )
            count += 1
        return count

    def get_catalog(self, source: str) -> dict[str, dict]:
        """Load catalog from MongoDB for a source.

        Returns:
            Dict of item_id -> item metadata
        """
        cursor = self.catalogs.find({"source": source})
        items = {}
        for doc in cursor:
            item_id = doc.pop("item_id", None)
            if item_id:
                doc.pop("_id", None)
                doc.pop("updated_at", None)
                items[item_id] = doc
        return items

    # ── Book Inventory ──────────────────────────────────────────────────────

    def load_book_inventory(self) -> list[dict]:
        """Load all books from book_inventory collection."""
        return list(self.book_inventory.find({}))

    def save_book_inventory(self, books: list[dict]) -> int:
        """Replace book inventory with given list. Returns count saved."""
        self.book_inventory.delete_many({})
        if books:
            # Strip _id from incoming dicts so MongoDB assigns new ones
            docs = []
            for b in books:
                d = dict(b)
                d.pop("_id", None)
                docs.append(d)
            self.book_inventory.insert_many(docs)
        return len(books)

    # ── Author Profiles ─────────────────────────────────────────────────────

    def load_author_profiles(self) -> list[dict]:
        """Load all author profiles."""
        return list(self.author_profiles.find({}))

    def save_author_profiles(self, profiles: list[dict]) -> int:
        """Replace author profiles with given list. Returns count saved."""
        self.author_profiles.delete_many({})
        if profiles:
            docs = []
            for p in profiles:
                d = dict(p)
                d.pop("_id", None)
                docs.append(d)
            self.author_profiles.insert_many(docs)
        return len(profiles)

    def save_author_chronology(self, events: list[dict]) -> int:
        """Replace author chronology events (schema: year, author, event, place, details). Returns count."""
        self.author_chronology.delete_many({})
        if events:
            docs = [dict(e) for e in events]
            self.author_chronology.insert_many(docs)
        return len(events)

    def save_author_bibliography(self, entries: list[dict]) -> int:
        """Replace author bibliography (schema: author, author_id, + work fields). Returns count."""
        self.author_bibliography.delete_many({})
        if entries:
            docs = [dict(e) for e in entries]
            self.author_bibliography.insert_many(docs)
        return len(entries)

    def save_author_research_summary(self, summary: dict) -> None:
        """Upsert single author research summary document (generated, total_authors, etc.)."""
        summary = dict(summary)
        summary.setdefault("generated", datetime.utcnow().isoformat())
        self.author_research_summary.delete_many({})
        self.author_research_summary.insert_one(summary)

    def save_author_timeline(self, timeline_doc: dict) -> None:
        """Replace author timeline document (timeline list + metadata)."""
        doc = dict(timeline_doc)
        doc.setdefault("metadata", {})["generated"] = datetime.utcnow().isoformat()
        self.author_timeline.delete_many({})
        self.author_timeline.insert_one(doc)

    def save_author_period_analysis(self, period_doc: dict) -> None:
        """Replace author period analysis document (periods dict + metadata)."""
        doc = dict(period_doc)
        doc.setdefault("generated", datetime.utcnow().isoformat())
        self.author_period_analysis.delete_many({})
        self.author_period_analysis.insert_one(doc)

    def save_author_generation_report(self, report_doc: dict) -> None:
        """Replace author generation report document."""
        doc = dict(report_doc)
        if "metadata" in doc:
            doc["metadata"]["generated"] = datetime.utcnow().isoformat()
        else:
            doc["generated"] = datetime.utcnow().isoformat()
        self.author_generation_report.delete_many({})
        self.author_generation_report.insert_one(doc)

    def save_coverage_gaps(self, report: dict) -> None:
        """Replace coverage gaps report (summary + gaps list)."""
        doc = dict(report)
        doc.setdefault("generated", datetime.utcnow().isoformat())
        self.coverage_gaps.delete_many({})
        self.coverage_gaps.insert_one(doc)

    def save_acquisition_priorities(self, priorities_by_filter: dict[str, list[dict]]) -> None:
        """Replace acquisition priorities (one doc: keys 'all', 'high', etc., each a list of row dicts)."""
        doc = {
            "generated": datetime.utcnow().isoformat(),
            **priorities_by_filter,
        }
        self.acquisition_priorities.delete_many({})
        self.acquisition_priorities.insert_one(doc)

    # ── Augmentation ────────────────────────────────────────────────────────

    def insert_augmented_document(
        self,
        source_doc: str,
        strategy: str,
        text: str,
        paragraph_index: int,
        task_uid: str,
    ) -> str:
        """Insert augmented text as a corpus document. Returns document ID."""
        return self.insert_document(
            source="augmented",
            title=f"{source_doc}::{strategy}::{paragraph_index}",
            text=text,
            metadata={
                "augmentation_strategy": strategy,
                "source_doc": source_doc,
                "paragraph_index": paragraph_index,
                "task_uid": task_uid,
            },
        )

    def is_augmentation_task_done(self, task_uid: str) -> bool:
        """Check if augmentation task is already completed."""
        return self.augmentation_checkpoint.count_documents({"task_uid": task_uid}) > 0

    def mark_augmentation_done(self, task_uid: str, record: dict) -> None:
        """Record completed augmentation task in checkpoint."""
        self.augmentation_checkpoint.update_one(
            {"task_uid": task_uid},
            {"$set": {**record, "task_uid": task_uid, "timestamp": datetime.utcnow()}},
            upsert=True,
        )

    def load_augmentation_checkpoint_uids(self) -> set[str]:
        """Load set of completed task UIDs for resume."""
        cursor = self.augmentation_checkpoint.find({}, {"task_uid": 1})
        return {doc["task_uid"] for doc in cursor}

    def insert_augmentation_metrics_report(
        self,
        batch_id: str,
        strategy_name: str,
        report: dict,
    ) -> str:
        """Insert augmentation metrics batch report. All metrics stored in MongoDB only."""
        doc = {
            "batch_id": batch_id,
            "strategy_name": strategy_name,
            "timestamp": datetime.utcnow(),
            **report,
        }
        result = self.augmentation_metrics.insert_one(doc)
        return str(result.inserted_id)

    def insert_augmentation_metric_card(
        self,
        text_id: str,
        strategy_name: str,
        card_dict: dict,
    ) -> str:
        """Insert a single metric card. Used for per-task metrics."""
        doc = {
            "text_id": text_id,
            "strategy_name": strategy_name,
            "timestamp": datetime.utcnow(),
            "card": card_dict,
        }
        result = self.augmentation_metrics.insert_one(doc)
        return str(result.inserted_id)

    # ── GridFS Source Binaries ───────────────────────────────────────────────

    def upload_source_binary(
        self,
        file_path: Path,
        source: str,
        metadata: Optional[dict] = None,
    ) -> Any:
        """Upload a PDF/image to GridFS. Returns file_id (ObjectId).

        Args:
            file_path: Local path to file
            source: Source identifier (e.g. mss_nkr, gomidas)
            metadata: Optional metadata (e.g. url, date, identifier)
        """
        fs = self.source_binaries_fs
        meta = {"source": source, **(metadata or {})}
        with open(file_path, "rb") as f:
            file_id = fs.put(
                f,
                filename=file_path.name,
                content_type=self._guess_content_type(file_path),
                metadata=meta,
            )
        return file_id

    def get_source_binary_stream(self, file_id: Any):
        """Open a read stream for a GridFS file. Use for OCR temp extraction."""
        return self.source_binaries_fs.open_download_stream(file_id)

    def download_source_binary_to_path(self, file_id: Any, dest_path: Path) -> None:
        """Stream GridFS file to local path. Caller should delete temp after use."""
        with self.source_binaries_fs.open_download_stream(file_id) as stream:
            dest_path.write_bytes(stream.read())

    def find_source_binaries(
        self,
        source: Optional[str] = None,
        limit: int = 0,
    ) -> list[dict]:
        """List source binaries in GridFS. Returns metadata dicts with _id, filename, source."""
        query = {"metadata.source": source} if source else {}
        cursor = self.source_binaries_fs.find(query)
        if limit > 0:
            cursor = cursor.limit(limit)
        return [
            {
                "_id": doc._id,
                "filename": getattr(doc, "filename", "unknown"),
                "source": (getattr(doc, "metadata", None) or {}).get("source", ""),
            }
            for doc in cursor
        ]

    def _guess_content_type(self, path: Path) -> str:
        ext = path.suffix.lower()
        m = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".tiff": "image/tiff", ".tif": "image/tiff"}
        return m.get(ext, "application/octet-stream")

    # ── Bulk Operations ─────────────────────────────────────────────────────

    def bulk_insert_from_files(
        self,
        source: str,
        file_paths: list[Path],
        metadata_extractor: Optional[Callable[[Path], dict]] = None,
        config: Optional[dict] = None,
    ) -> dict:
        """Bulk insert documents from text files.

        Uses insert_or_skip when ingestion._shared.helpers is available so document_metrics
        (e.g. word_counts) are computed on ingest.

        Args:
            source: Source identifier
            file_paths: List of .txt file paths
            metadata_extractor: Optional function(path) -> dict to extract metadata
            config: Optional pipeline config (for compute_metrics_on_ingest)

        Returns:
            Dictionary with {"inserted": int, "duplicates": int, "errors": int}
        """
        try:
            from ingestion._shared.helpers import insert_or_skip
        except ImportError:
            insert_or_skip = None
        stats = {"inserted": 0, "duplicates": 0, "errors": 0}
        cfg = config or {}

        for path in file_paths:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                title = path.stem

                if metadata_extractor:
                    extra_metadata = metadata_extractor(path)
                else:
                    extra_metadata = {}

                metadata = {"file_path": str(path), **extra_metadata}

                if insert_or_skip is not None:
                    ok = insert_or_skip(
                        self,
                        source=source,
                        title=title,
                        text=text,
                        metadata=metadata,
                        config=cfg,
                    )
                    if ok:
                        stats["inserted"] += 1
                    else:
                        stats["duplicates"] += 1
                else:
                    self.insert_document(
                        source=source,
                        title=title,
                        text=text,
                        metadata=metadata,
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
