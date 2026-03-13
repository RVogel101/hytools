"""Database adapters for scrapers - enables direct SQLite writes from scraper modules."""

import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from .connection import DatabaseConnection
from .telemetry import ProcessTelemetry


class NewspaperDatabaseAdapter:
    """Adapter for newspaper scraper to write directly to SQLite."""

    def __init__(self, db: DatabaseConnection, telemetry: Optional[ProcessTelemetry] = None):
        """Initialize adapter.
        
        Args:
            db: DatabaseConnection instance
            telemetry: Optional ProcessTelemetry for logging
        """
        self.db = db
        self.telemetry = telemetry

    def insert_article(
        self,
        operation_id: str,
        source_name: str,
        url: str,
        title: Optional[str],
        content: Optional[str],
        author: Optional[str] = None,
        published_date: Optional[str] = None,
    ) -> bool:
        """Insert newspaper article to database."""
        article_id = f"{source_name}_{hashlib.md5(url.encode()).hexdigest()[:12]}"
        success = self.db.insert_newspaper_article(
            article_id=article_id,
            source_name=source_name,
            url=url,
            title=title,
            content=content,
            author=author,
            published_date=published_date,
            operation_id=operation_id,
        )

        if success and self.telemetry:
            self.telemetry.update_record_counts(operation_id, attempted=1, imported=1)

        return success

    def check_duplicate(self, content: Optional[str]) -> bool:
        """Check if article with this content already exists."""
        if not content:
            return False
        content_sha1 = hashlib.sha1(content.encode()).hexdigest()
        return self.db.newspaper_dedup_check(content_sha1)


class NayiriDatabaseAdapter:
    """Adapter for Nayiri dictionary scraper to write directly to SQLite."""

    def __init__(self, db: DatabaseConnection, telemetry: Optional[ProcessTelemetry] = None):
        self.db = db
        self.telemetry = telemetry

    def insert_entry(
        self,
        operation_id: str,
        headword: str,
        definition: Optional[str] = None,
        pronunciation: Optional[str] = None,
        part_of_speech: Optional[str] = None,
        examples: Optional[str] = None,
        etymology: Optional[str] = None,
    ) -> bool:
        """Insert dictionary entry to database."""
        success = self.db.insert_nayiri_entry(
            entry_id=f"nayiri_{hashlib.md5(headword.encode()).hexdigest()[:8]}",
            headword=headword,
            definition=definition,
            pronunciation=pronunciation,
            part_of_speech=part_of_speech,
            examples=examples,
            etymology=etymology,
            operation_id=operation_id,
        )

        if success and self.telemetry:
            self.telemetry.update_record_counts(operation_id, attempted=1, imported=1)

        return success

    def check_duplicate(self, headword: str, definition: Optional[str] = None) -> bool:
        """Check if entry with this content already exists."""
        content_combined = f"{headword}|{definition or ''}"
        content_sha1 = hashlib.sha1(content_combined.encode()).hexdigest()
        return self.db.nayiri_dedup_check(content_sha1)


class ArchiveOrgDatabaseAdapter:
    """Adapter for archive.org scraper to write directly to SQLite."""

    def __init__(self, db: DatabaseConnection, telemetry: Optional[ProcessTelemetry] = None):
        self.db = db
        self.telemetry = telemetry

    def insert_text(
        self,
        operation_id: str,
        archive_id: str,
        title: Optional[str],
        author: Optional[str],
        publication_date: Optional[str],
        full_text: Optional[str],
        extracted_from_format: str = "uncertain",
        source_url: Optional[str] = None,
    ) -> bool:
        """Insert archive.org text to database."""
        success = self.db.insert_archive_org_text(
            text_id=f"archive_{archive_id[:50]}",
            archive_id=archive_id,
            title=title,
            author=author,
            publication_date=publication_date,
            full_text=full_text,
            extracted_from_format=extracted_from_format,
            source_url=source_url,
            operation_id=operation_id,
        )

        if success and self.telemetry:
            self.telemetry.update_record_counts(operation_id, attempted=1, imported=1)

        return success

    def check_duplicate(self, content: Optional[str]) -> bool:
        """Check if text with this content already exists."""
        if not content:
            return False
        content_sha1 = hashlib.sha1(content.encode()).hexdigest()
        return self.db.archive_org_dedup_check(content_sha1)


class GenericDatabaseAdapter:
    """Generic adapter for inserting texts into various tables."""

    def __init__(self, db: DatabaseConnection, telemetry: Optional[ProcessTelemetry] = None):
        self.db = db
        self.telemetry = telemetry

    def insert_generic_text(
        self,
        operation_id: str,
        table_name: str,
        source_type: str,
        unique_id: str,
        content: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Insert text into appropriate table based on source type.
        
        Args:
            operation_id: Ingestion operation ID
            table_name: Target table (e.g., 'wikipedia_articles', 'culturax_texts')
            source_type: Source type for context
            unique_id: Unique identifier for record
            content: Text content
            metadata: Additional metadata (title, author, url, etc.)
            
        Returns:
            True if successful
        """
        metadata = metadata or {}
        content_sha1 = hashlib.sha1(content.encode()).hexdigest() if content else None
        content_length = len(content) if content else 0

        sql = f"""
        INSERT INTO {table_name} (
            {source_type}_id, url, title, content, author,
            content_sha1, content_length_chars, source_url,
            scraped_timestamp, operation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            unique_id,
            metadata.get("url"),
            metadata.get("title"),
            content,
            metadata.get("author"),
            content_sha1,
            content_length,
            metadata.get("source_url") or metadata.get("url"),
            datetime.now().isoformat(),
            operation_id,
        )

        try:
            self.db.execute(sql, params)
            self.db.commit()
            if self.telemetry:
                self.telemetry.update_record_counts(operation_id, attempted=1, imported=1)
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to insert generic text: {e}")
            if self.telemetry:
                self.telemetry.update_record_counts(operation_id, attempted=1, failed=1)
            return False
