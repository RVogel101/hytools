"""Tests for book inventory system (moved from WesternArmenianLLM)."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from ingestion.discovery.book_inventory import (
    BookAuthor,
    BookInventoryEntry,
    BookInventoryManager,
    ContentType,
    CoverageStatus,
    LanguageVariant,
)


class TestBookInventoryEntry(TestCase):
    """Test book inventory entry creation and operations."""

    def test_create_basic_entry(self):
        """Test creating a basic book entry."""
        book = BookInventoryEntry(
            title="Test Book",
            first_publication_year=1999,
        )

        self.assertEqual(book.title, "Test Book")
        self.assertEqual(book.first_publication_year, 1999)
        self.assertEqual(book.coverage_status, CoverageStatus.MISSING)

    def test_create_entry_with_authors(self):
        """Test creating entry with author information."""
        authors = [
            BookAuthor(name="Testing Author", birth_year=1950),
        ]

        book = BookInventoryEntry(
            title="Test Book",
            authors=authors,
        )

        self.assertEqual(len(book.authors), 1)
        self.assertEqual(book.authors[0].name, "Testing Author")
        self.assertEqual(book.authors[0].birth_year, 1950)

    def test_entry_to_dict_serialization(self):
        """Test converting entry to dictionary."""
        book = BookInventoryEntry(
            title="Test",
            content_type=ContentType.POETRY_COLLECTION,
            coverage_status=CoverageStatus.IN_CORPUS,
            language_variant=LanguageVariant.WESTERN,
        )

        data = book.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["title"], "Test")
        self.assertEqual(data["content_type"], "poetry_collection")
        self.assertEqual(data["coverage_status"], "in_corpus")
        self.assertEqual(data["language_variant"], "western")


class TestBookInventoryManager(TestCase):
    """Test inventory management operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.inventory_file = str(Path(self.temp_dir.name) / "test_inventory.jsonl")

    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()

    def test_manager_initialization(self):
        """Test manager initializes without errors."""
        manager = BookInventoryManager(self.inventory_file)

        self.assertIsNotNone(manager)
        self.assertEqual(len(manager.books), 0)

    def test_add_single_book(self):
        """Test adding a book to manager."""
        manager = BookInventoryManager(self.inventory_file)

        book = BookInventoryEntry(
            title="Test Book",
            content_type=ContentType.NOVEL,
        )

        manager.add_book(book)

        self.assertEqual(len(manager.books), 1)
        self.assertEqual(manager.books[0].title, "Test Book")

    def test_add_batch_of_books(self):
        """Test adding multiple books."""
        manager = BookInventoryManager(self.inventory_file)

        books = [
            BookInventoryEntry(title=f"Book {i}", content_type=ContentType.NOVEL)
            for i in range(5)
        ]

        manager.add_books_batch(books)

        self.assertEqual(len(manager.books), 5)

    def test_find_by_title(self):
        """Test finding books by title."""
        manager = BookInventoryManager(self.inventory_file)

        manager.add_book(BookInventoryEntry(title="Unique Title 123"))
        manager.add_book(BookInventoryEntry(title="Another Book"))

        results = manager.find_by_title("Unique Title 123")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Unique Title 123")

    def test_find_by_author(self):
        """Test finding books by author."""
        manager = BookInventoryManager(self.inventory_file)

        book1 = BookInventoryEntry(
            title="Book 1",
            authors=[BookAuthor(name="Test Author")],
        )
        book2 = BookInventoryEntry(
            title="Book 2",
            authors=[BookAuthor(name="Other Author")],
        )

        manager.add_books_batch([book1, book2])

        results = manager.find_by_author("Test Author")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Book 1")

    def test_save_and_load_inventory(self):
        """Test saving and loading inventory."""
        manager1 = BookInventoryManager(self.inventory_file)

        book = BookInventoryEntry(
            title="Persistent Book",
            first_publication_year=2000,
            content_type=ContentType.ESSAYS,
        )

        manager1.add_book(book)
        manager1.save_inventory()

        manager2 = BookInventoryManager(self.inventory_file)

        self.assertEqual(len(manager2.books), 1)
        self.assertEqual(manager2.books[0].title, "Persistent Book")

    def test_export_to_csv(self):
        """Test exporting to CSV format."""
        manager = BookInventoryManager(self.inventory_file)

        books = [
            BookInventoryEntry(
                title=f"Book {i}",
                authors=[BookAuthor(name=f"Author {i}")],
                first_publication_year=1990 + i,
                coverage_status=CoverageStatus.IN_CORPUS,
            )
            for i in range(3)
        ]

        manager.add_books_batch(books)

        csv_path = Path(self.temp_dir.name) / "test_export.csv"
        result = manager.export_to_csv(str(csv_path))

        self.assertTrue(result.exists())

        with open(result, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 4)
        self.assertIn("title", lines[0])
        self.assertIn("Book 0", lines[1])

    def test_export_summary_report(self):
        """Test exporting summary report."""
        manager = BookInventoryManager(self.inventory_file)

        manager.add_book(BookInventoryEntry(
            title="Book 1",
            coverage_status=CoverageStatus.IN_CORPUS,
            estimated_word_count=50000,
            content_type=ContentType.NOVEL,
        ))
        manager.add_book(BookInventoryEntry(
            title="Book 2",
            coverage_status=CoverageStatus.MISSING,
            estimated_word_count=30000,
            content_type=ContentType.POETRY_COLLECTION,
        ))

        report_path = Path(self.temp_dir.name) / "summary.json"
        result = manager.export_summary_report(str(report_path))

        self.assertTrue(result.exists())

        with open(result, "r", encoding="utf-8") as f:
            report = json.load(f)

        self.assertEqual(report["total_books"], 2)
        self.assertEqual(report["by_status"]["in_corpus"], 1)
        self.assertEqual(report["by_status"]["missing"], 1)
        self.assertEqual(report["word_counts"]["total_estimated"], 80000)
        self.assertEqual(report["word_counts"]["in_corpus"], 50000)

    def test_get_summary_statistics(self):
        """Test summary statistics computation."""
        manager = BookInventoryManager(self.inventory_file)

        for i in range(3):
            manager.add_book(BookInventoryEntry(
                title=f"Book {i}",
                authors=[BookAuthor(name="Author A" if i < 2 else "Author B")],
                content_type=ContentType.NOVEL if i == 0 else ContentType.POETRY_COLLECTION,
                coverage_status=CoverageStatus.IN_CORPUS if i == 0 else CoverageStatus.MISSING,
                estimated_word_count=50000,
                first_publication_year=1990 + (i * 10),
            ))

        summary = manager.get_summary()

        self.assertEqual(summary.total_books, 3)
        self.assertEqual(summary.books_in_corpus, 1)
        self.assertEqual(summary.books_missing, 2)
        self.assertIn("Author A", summary.books_by_author)
        self.assertEqual(summary.books_by_author["Author A"], 2)


class TestCoverageStatus(TestCase):
    """Test coverage status enum."""

    def test_coverage_status_values(self):
        """Test coverage status enum values."""
        self.assertEqual(CoverageStatus.IN_CORPUS.value, "in_corpus")
        self.assertEqual(CoverageStatus.MISSING.value, "missing")
        self.assertEqual(CoverageStatus.PARTIALLY_SCANNED.value, "partially_scanned")


class TestContentType(TestCase):
    """Test content type enum."""

    def test_content_type_values(self):
        """Test content type enum values."""
        self.assertEqual(ContentType.NOVEL.value, "novel")
        self.assertEqual(ContentType.POETRY_COLLECTION.value, "poetry_collection")
        self.assertEqual(ContentType.ESSAYS.value, "essays")


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
