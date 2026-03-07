"""Migrate existing scraper output files (JSONL/text) to SQLite database."""

import json
import logging
from pathlib import Path
from typing import Optional, Generator, Dict, Any
import hashlib
from datetime import datetime

from .connection import DatabaseConnection

logger = logging.getLogger(__name__)


class DataMigrator:
    """Migrates data from JSONL checkpoints and text files to SQLite."""

    def __init__(self, db: DatabaseConnection):
        """Initialize migrator with database connection."""
        self.db = db

    # ========================================================================
    # Newspaper migration
    # ========================================================================
    def migrate_newspaper_checkpoint(
        self,
        checkpoint_path: Path,
        source_name: str,
        dedup_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Migrate newspaper checkpoint JSONL to SQLite.
        
        Args:
            checkpoint_path: Path to checkpoint JSONL file
            source_name: Name of newspaper source (e.g., "Aztag", "Horizon")
            dedup_enabled: Whether to skip articles with duplicate content
            
        Returns:
            Dict with migration stats: {imported, skipped, errors, migration_id}
        """
        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint file not found: {checkpoint_path}")
            return {"imported": 0, "skipped": 0, "errors": 0, "migration_id": None}

        operation_id = self.db.start_ingestion_operation(
            source_type="newspaper",
            source_name=source_name,
            description=f"Migrating {checkpoint_path.name}",
        )

        imported, skipped, errors = 0, 0, 0

        try:
            for article in self._read_jsonl(checkpoint_path):
                try:
                    # Extract article data
                    article_id = article.get("article_id") or article.get("url", "").replace("/", "_")[:100]
                    url = article.get("url")
                    title = article.get("title")
                    content = article.get("content") or article.get("text")
                    author = article.get("author")
                    pub_date = article.get("published_date") or article.get("pub_date")

                    if not url:
                        logger.warning(f"Skipping article without URL: {article}")
                        skipped += 1
                        continue

                    # Dedup check
                    if content and dedup_enabled:
                        content_sha1 = hashlib.sha1(content.encode()).hexdigest()
                        if self.db.newspaper_dedup_check(content_sha1):
                            logger.debug(f"Skipping duplicate article: {url}")
                            skipped += 1
                            continue

                    # Insert into DB
                    if self.db.insert_newspaper_article(
                        article_id=article_id,
                        source_name=source_name,
                        url=url,
                        title=title,
                        content=content,
                        author=author,
                        published_date=pub_date,
                        operation_id=operation_id,
                    ):
                        imported += 1
                    else:
                        skipped += 1

                except Exception as e:
                    logger.error(f"Error importing article: {e}")
                    errors += 1

            self.db.end_ingestion_operation(operation_id, status="success")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.db.end_ingestion_operation(operation_id, status="failed", error_message=str(e))
            errors += 1

        # Log migration
        migration_id = self.db.log_migration(
            source_file=str(checkpoint_path),
            source_type="newspaper",
            target_table="newspaper_articles",
            record_count=imported,
            status="success" if errors == 0 else "partial",
        )

        logger.info(
            f"Newspaper migration complete: {imported} imported, {skipped} skipped, {errors} errors "
            f"(file: {checkpoint_path.name})"
        )

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "migration_id": migration_id,
        }

    # ========================================================================
    # Nayiri migration
    # ========================================================================
    def migrate_nayiri_checkpoint(
        self,
        checkpoint_path: Path,
        dedup_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Migrate Nayiri checkpoint JSONL to SQLite."""
        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint file not found: {checkpoint_path}")
            return {"imported": 0, "skipped": 0, "errors": 0, "migration_id": None}

        operation_id = self.db.start_ingestion_operation(
            source_type="nayiri",
            source_name="nayiri.com",
            description=f"Migrating {checkpoint_path.name}",
        )

        imported, skipped, errors = 0, 0, 0

        try:
            for entry in self._read_jsonl(checkpoint_path):
                try:
                    headword = entry.get("headword") or entry.get("word")
                    if not headword:
                        skipped += 1
                        continue
                    entry_id = f"nayiri_{hashlib.md5(headword.encode()).hexdigest()[:8]}"

                    # Dedup check
                    if dedup_enabled:
                        definition = entry.get("definition") or ""
                        content_combined = f"{headword}|{definition}"
                        content_sha1 = hashlib.sha1(content_combined.encode()).hexdigest()
                        if self.db.nayiri_dedup_check(content_sha1):
                            logger.debug(f"Skipping duplicate entry: {headword}")
                            skipped += 1
                            continue

                    if self.db.insert_nayiri_entry(
                        entry_id=entry_id,
                        headword=headword,
                        definition=entry.get("definition"),
                        pronunciation=entry.get("pronunciation"),
                        part_of_speech=entry.get("part_of_speech") or entry.get("pos"),
                        examples=entry.get("examples"),
                        etymology=entry.get("etymology"),
                        operation_id=operation_id,
                    ):
                        imported += 1
                    else:
                        skipped += 1

                except Exception as e:
                    logger.error(f"Error importing Nayiri entry: {e}")
                    errors += 1

            self.db.end_ingestion_operation(operation_id, status="success")

        except Exception as e:
            logger.error(f"Nayiri migration failed: {e}")
            self.db.end_ingestion_operation(operation_id, status="failed", error_message=str(e))
            errors += 1

        migration_id = self.db.log_migration(
            source_file=str(checkpoint_path),
            source_type="nayiri",
            target_table="nayiri_entries",
            record_count=imported,
            status="success" if errors == 0 else "partial",
        )

        logger.info(
            f"Nayiri migration complete: {imported} imported, {skipped} skipped, {errors} errors "
            f"(file: {checkpoint_path.name})"
        )

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "migration_id": migration_id,
        }

    # ========================================================================
    # Archive.org migration
    # ========================================================================
    def migrate_archive_org_texts(
        self,
        checkpoint_path: Path,
        dedup_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Migrate archive.org checkpoint JSONL to SQLite."""
        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint file not found: {checkpoint_path}")
            return {"imported": 0, "skipped": 0, "errors": 0, "migration_id": None}

        operation_id = self.db.start_ingestion_operation(
            source_type="archive_org",
            source_name="archive.org",
            description=f"Migrating {checkpoint_path.name}",
        )

        imported, skipped, errors = 0, 0, 0

        try:
            for record in self._read_jsonl(checkpoint_path):
                try:
                    archive_id = record.get("archive_id") or record.get("id", "unknown")
                    text_id = f"archive_{archive_id[:50]}"
                    full_text = record.get("full_text") or record.get("text") or record.get("content")

                    # Dedup check
                    if full_text and dedup_enabled:
                        content_sha1 = hashlib.sha1(full_text.encode()).hexdigest()
                        if self.db.archive_org_dedup_check(content_sha1):
                            logger.debug(f"Skipping duplicate archive text: {archive_id}")
                            skipped += 1
                            continue

                    if self.db.insert_archive_org_text(
                        text_id=text_id,
                        archive_id=archive_id,
                        title=record.get("title"),
                        author=record.get("author"),
                        publication_date=record.get("publication_date") or record.get("pub_date"),
                        full_text=full_text,
                        extracted_from_format=record.get("format", "uncertain"),
                        source_url=record.get("url"),
                        operation_id=operation_id,
                    ):
                        imported += 1
                    else:
                        skipped += 1

                except Exception as e:
                    logger.error(f"Error importing archive.org text: {e}")
                    errors += 1

            self.db.end_ingestion_operation(operation_id, status="success")

        except Exception as e:
            logger.error(f"Archive.org migration failed: {e}")
            self.db.end_ingestion_operation(operation_id, status="failed", error_message=str(e))
            errors += 1

        migration_id = self.db.log_migration(
            source_file=str(checkpoint_path),
            source_type="archive_org",
            target_table="archive_org_texts",
            record_count=imported,
            status="success" if errors == 0 else "partial",
        )

        logger.info(
            f"Archive.org migration complete: {imported} imported, {skipped} skipped, {errors} errors "
            f"(file: {checkpoint_path.name})"
        )

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "migration_id": migration_id,
        }

    # ========================================================================
    # Helper utilities
    # ========================================================================
    @staticmethod
    def _read_jsonl(path: Path) -> Generator[Dict[str, Any], None, None]:
        """Read JSONL file and yield records."""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON line in {path}: {e}")
                    continue
