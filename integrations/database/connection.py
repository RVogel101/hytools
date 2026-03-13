"""SQLite database connection for corpus ingestion operations.

Migrated from WesternArmenianLLM/src/database/connection.py.
Removed the dependency on src.config_loader — path resolution is now
explicit-argument only (no implicit config/env fallback).
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .corpus_schema import get_corpus_schema_sql

logger = logging.getLogger(__name__)

_DEFAULT_DB_NAME = "western_armenian.db"


class CorpusDatabase:
    """Manages SQLite connections and CRUD for the corpus ingestion schema."""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = Path.cwd() / "data" / _DEFAULT_DB_NAME
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_schema()

    # ─── Context manager ──────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ─── Connection lifecycle ─────────────────────────────────────

    def connect(self):
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        logger.debug("Connected to database: %s", self.db_path)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_schema(self):
        temp_conn = sqlite3.connect(str(self.db_path))
        try:
            temp_conn.executescript(get_corpus_schema_sql())
            temp_conn.commit()
            logger.info("Database schema initialized: %s", self.db_path)
        except sqlite3.DatabaseError as e:
            logger.error("Failed to initialize schema: %s", e)
            raise
        finally:
            temp_conn.close()

    # ─── Generic execute helpers ──────────────────────────────────

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        if not self._conn:
            self.connect()
        assert self._conn is not None
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]):
        if not self._conn:
            self.connect()
        assert self._conn is not None
        self._conn.executemany(sql, params_list)

    def commit(self):
        if self._conn:
            self._conn.commit()

    def get_one(self, sql: str, params: tuple = ()):
        return self.execute(sql, params).fetchone()

    def get_all(self, sql: str, params: tuple = ()):
        return self.execute(sql, params).fetchall()

    # ─── Newspaper operations ─────────────────────────────────────

    def insert_newspaper_article(
        self,
        article_id: str,
        source_name: str,
        url: str,
        title: Optional[str],
        content: Optional[str],
        author: Optional[str] = None,
        published_date: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> bool:
        content_sha1 = hashlib.sha1(content.encode()).hexdigest() if content else None
        content_length = len(content) if content else 0
        sql = """
        INSERT INTO newspaper_articles (
            article_id, source_name, url, title, content,
            author, published_date_raw, content_sha1, content_length_chars,
            scraped_timestamp, operation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            self.execute(
                sql,
                (
                    article_id, source_name, url, title, content,
                    author, published_date, content_sha1, content_length,
                    datetime.now().isoformat(), operation_id,
                ),
            )
            self.commit()
            return True
        except sqlite3.IntegrityError as e:
            logger.warning("Failed to insert article %s: %s", article_id, e)
            return False

    def get_newspaper_articles_by_source(self, source_name: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM newspaper_articles WHERE source_name = ? ORDER BY scraped_timestamp DESC"
        rows = self.get_all(sql, (source_name,))
        return [dict(row) for row in rows] if rows else []

    def newspaper_dedup_check(self, content_sha1: str) -> bool:
        sql = "SELECT COUNT(*) FROM newspaper_articles WHERE content_sha1 = ?"
        result = self.get_one(sql, (content_sha1,))
        return result[0] > 0 if result else False

    # ─── Nayiri dictionary operations ─────────────────────────────

    def insert_nayiri_entry(
        self,
        entry_id: str,
        headword: str,
        definition: Optional[str] = None,
        pronunciation: Optional[str] = None,
        part_of_speech: Optional[str] = None,
        examples: Optional[str] = None,
        etymology: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> bool:
        content_combined = f"{headword}|{definition or ''}|{pronunciation or ''}"
        content_sha1 = hashlib.sha1(content_combined.encode()).hexdigest()
        sql = """
        INSERT INTO nayiri_entries (
            entry_id, headword, definition, pronunciation,
            part_of_speech, examples, etymology, content_sha1,
            scraped_timestamp, operation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            self.execute(
                sql,
                (
                    entry_id, headword, definition, pronunciation,
                    part_of_speech, examples, etymology, content_sha1,
                    datetime.now().isoformat(), operation_id,
                ),
            )
            self.commit()
            return True
        except sqlite3.IntegrityError as e:
            logger.warning("Failed to insert Nayiri entry %s: %s", entry_id, e)
            return False

    def nayiri_dedup_check(self, content_sha1: str) -> bool:
        sql = "SELECT COUNT(*) FROM nayiri_entries WHERE content_sha1 = ?"
        result = self.get_one(sql, (content_sha1,))
        return result[0] > 0 if result else False

    # ─── Archive.org operations ───────────────────────────────────

    def insert_archive_org_text(
        self,
        text_id: str,
        archive_id: str,
        title: Optional[str],
        author: Optional[str],
        publication_date: Optional[str],
        full_text: Optional[str],
        extracted_from_format: str = "uncertain",
        source_url: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> bool:
        content_sha1 = hashlib.sha1(full_text.encode()).hexdigest() if full_text else None
        content_length = len(full_text) if full_text else 0
        sql = """
        INSERT INTO archive_org_texts (
            text_id, archive_id, title, author, publication_date,
            full_text, extracted_from_format, source_url, content_sha1,
            content_length_chars, scraped_timestamp, operation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            self.execute(
                sql,
                (
                    text_id, archive_id, title, author, publication_date,
                    full_text, extracted_from_format, source_url, content_sha1,
                    content_length, datetime.now().isoformat(), operation_id,
                ),
            )
            self.commit()
            return True
        except sqlite3.IntegrityError as e:
            logger.warning("Failed to insert archive.org text %s: %s", text_id, e)
            return False

    def archive_org_dedup_check(self, content_sha1: str) -> bool:
        sql = "SELECT COUNT(*) FROM archive_org_texts WHERE content_sha1 = ?"
        result = self.get_one(sql, (content_sha1,))
        return result[0] > 0 if result else False

    # ─── Ingestion & migration operations ─────────────────────────

    def start_ingestion_operation(
        self,
        source_type: str,
        source_name: str,
        description: Optional[str] = None,
        config_snapshot: Optional[dict] = None,
    ) -> str:
        operation_id = f"{source_type}_{source_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config_json = json.dumps(config_snapshot) if config_snapshot else None
        sql = """
        INSERT INTO ingestion_operations (
            operation_id, source_type, source_name, status, description, config_snapshot
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        self.execute(sql, (operation_id, source_type, source_name, "running", description, config_json))
        self.commit()
        return operation_id

    def end_ingestion_operation(
        self, operation_id: str, status: str = "success", error_message: Optional[str] = None
    ):
        sql = "UPDATE ingestion_operations SET status = ?, error_message = ? WHERE operation_id = ?"
        self.execute(sql, (status, error_message, operation_id))
        self.commit()

    def log_migration(
        self,
        source_file: str,
        source_type: str,
        target_table: str,
        record_count: int,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> str:
        migration_id = f"mig_{Path(source_file).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        sql = """
        INSERT INTO migration_log (
            migration_id, source_file, source_type, target_table,
            record_count, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.execute(sql, (migration_id, source_file, source_type, target_table, record_count, status, error_message))
        self.commit()
        return migration_id

    def mark_migration_file_deleted(self, migration_id: str):
        sql = "UPDATE migration_log SET file_deleted = TRUE, file_delete_timestamp = ? WHERE migration_id = ?"
        self.execute(sql, (datetime.now().isoformat(), migration_id))
        self.commit()

    def get_table_statistics(self) -> Dict[str, int]:
        tables = [
            "newspaper_articles", "nayiri_entries", "archive_org_texts",
            "wikipedia_articles", "culturax_texts", "hathitrust_texts",
            "loc_texts", "wikisource_texts",
        ]
        stats = {}
        for table in tables:
            result = self.get_one(f"SELECT COUNT(*) FROM {table}")
            stats[table] = result[0] if result else 0
        return stats


# Alias for backwards-compatibility with WesternArmenianLLM codebase
DatabaseConnection = CorpusDatabase
