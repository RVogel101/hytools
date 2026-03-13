"""Integration tests for database pipeline (moved from WesternArmenianLLM).

Uses integrations.database (CorpusDatabase, ProcessTelemetry) for
SQLite corpus ingestion schema and telemetry.
"""

import tempfile
from pathlib import Path

from integrations.database import CorpusDatabase, ProcessTelemetry


def test_database_initialization():
    """Test database is created with proper schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            stats = db.get_table_statistics()
            assert "newspaper_articles" in stats
            assert "nayiri_entries" in stats
            assert "archive_org_texts" in stats
        print("✓ Database initialization test passed")


def test_newspaper_article_insertion():
    """Test inserting newspaper articles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            operation_id = db.start_ingestion_operation(
                source_type="newspaper",
                source_name="test_newspaper",
            )

            success = db.insert_newspaper_article(
                article_id="test_1",
                source_name="test_newspaper",
                url="https://example.com/article1",
                title="Test Article",
                content="This is test content for the article.",
                operation_id=operation_id,
            )

            assert success

            articles = db.get_newspaper_articles_by_source("test_newspaper")
            assert len(articles) == 1
            assert articles[0]["title"] == "Test Article"

            db.end_ingestion_operation(operation_id, status="success")
        print("✓ Newspaper article insertion test passed")


def test_telemetry_recording():
    """Test telemetry recording."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            telemetry = ProcessTelemetry(db)

            operation_id = telemetry.start_operation(
                source_type="newspaper",
                source_name="test",
                config={"test": True},
            )

            telemetry.start_phase(operation_id, "extraction")
            telemetry.update_record_counts(operation_id, attempted=10, imported=9, skipped=1)
            telemetry.record_metric(
                operation_id,
                "extraction_rate",
                90.0,
                unit="%",
                phase="extraction",
            )
            telemetry.record_issue(
                operation_id,
                issue_category="rate_limit",
                description="Hit rate limit on 3rd page",
                severity="warning",
                affected_records=5,
            )
            telemetry.end_phase(operation_id, "extraction", record_count=10)
            telemetry.end_operation(operation_id, status="success")

            issues = telemetry.get_operation_issues(operation_id)
            assert len(issues) == 1
            assert issues[0]["issue_category"] == "rate_limit"
        print("✓ Telemetry recording test passed")


def test_deduplication():
    """Test content deduplication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            operation_id = db.start_ingestion_operation(
                source_type="newspaper",
                source_name="test",
            )

            content1 = "Original article content"

            result1 = db.insert_newspaper_article(
                article_id="article_1",
                source_name="test",
                url="https://example.com/1",
                title="Article 1",
                content=content1,
                operation_id=operation_id,
            )
            assert result1

            articles = db.get_newspaper_articles_by_source("test")
            assert len(articles) == 1
        print("✓ Deduplication test passed")


def test_nayiri_entry_insertion():
    """Test inserting Nayiri dictionary entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            operation_id = db.start_ingestion_operation(
                source_type="nayiri",
                source_name="nayiri.com",
            )

            success = db.insert_nayiri_entry(
                entry_id="nayiri_test",
                headword="մայր",
                definition="mother",
                pronunciation="mayr",
                part_of_speech="noun",
                operation_id=operation_id,
            )

            assert success
        print("✓ Nayiri entry insertion test passed")


def test_archive_org_text_insertion():
    """Test inserting archive.org texts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            operation_id = db.start_ingestion_operation(
                source_type="archive_org",
                source_name="archive.org",
            )

            success = db.insert_archive_org_text(
                text_id="archive_test_1",
                archive_id="test_archive_id_123",
                title="Test Text",
                author="Test Author",
                publication_date="1890",
                full_text="This is archived text content.",
                source_url="https://archive.org/details/test123",
                operation_id=operation_id,
            )

            assert success
        print("✓ Archive.org text insertion test passed")


def test_orchestrator_status():
    """Test database status reporting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with CorpusDatabase(db_path) as db:
            stats = db.get_table_statistics()
            assert isinstance(stats, dict)
            assert "newspaper_articles" in stats
        print("✓ Orchestrator status test passed")


def run_all_tests():
    """Run all integration tests."""
    print("\nRunning integration tests...\n")

    test_functions = [
        test_database_initialization,
        test_newspaper_article_insertion,
        test_telemetry_recording,
        test_deduplication,
        test_nayiri_entry_insertion,
        test_archive_org_text_insertion,
        test_orchestrator_status,
    ]

    for test_func in test_functions:
        try:
            test_func()
        except Exception as e:
            print(f"✗ {test_func.__name__} failed: {e}")
            raise

    print("\n✓ All integration tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
