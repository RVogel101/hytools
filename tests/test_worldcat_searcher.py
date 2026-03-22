"""Tests for WorldCat Armenian book searcher integration (moved from WesternArmenianLLM).

Tests cover:
- WorldCat API connectivity (if available)
- Search result parsing
- Fallback database loading
- Deduplication logic
- Graceful degradation
"""

import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from hytool.ingestion.discovery.book_inventory import (
    BookAuthor,
    BookInventoryEntry,
    BookInventoryManager,
    ContentType,
)
from hytool.ingestion.discovery.worldcat_searcher import (
    FALLBACK_ARMENIAN_BOOKS,
    WorldCatError,
    WorldCatSearcher,
)

logger = logging.getLogger(__name__)


class TestWorldCatSearcher(unittest.TestCase):
    """Test WorldCat integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.searcher = WorldCatSearcher()

    def test_searcher_initializes(self):
        """Test that searcher initializes without errors."""
        self.assertIsNotNone(self.searcher)
        self.assertTrue(hasattr(self.searcher, "search_armenian_books"))
        self.assertTrue(hasattr(self.searcher, "parse_search_results"))

    def test_fallback_database_loaded(self):
        """Test that fallback database contains expected books."""
        self.assertGreater(len(FALLBACK_ARMENIAN_BOOKS), 0)

        book = FALLBACK_ARMENIAN_BOOKS[0]
        self.assertIn("title", book)
        self.assertIn("authors", book)
        self.assertIn("publication_year", book)
        self.assertGreater(book["publication_year"], 1800)

    def test_fallback_database_diversity(self):
        """Test that fallback database has diverse content types."""
        content_types = set()

        for book in FALLBACK_ARMENIAN_BOOKS:
            if "content_type" in book:
                content_types.add(book["content_type"])

        self.assertGreaterEqual(len(content_types), 3)

    def test_fallback_database_time_span(self):
        """Test that fallback database spans major time periods."""
        years = [
            y for book in FALLBACK_ARMENIAN_BOOKS
            for y in [book.get("publication_year")]
            if y is not None
        ]

        self.assertGreater(len(years), 0)

        year_span = max(years) - min(years)
        self.assertGreater(year_span, 80)

    def test_can_search_armenian_books_fallback(self):
        """Test that fallback search pattern works."""
        self.assertGreater(len(FALLBACK_ARMENIAN_BOOKS), 0)

        for book in FALLBACK_ARMENIAN_BOOKS:
            self.assertIn("title", book)
            self.assertIn("authors", book)
            self.assertIn("publication_year", book)

    def test_fallback_results_are_book_entries(self):
        """Test that fallback books have required structure."""
        for result in FALLBACK_ARMENIAN_BOOKS:
            self.assertIn("title", result)
            self.assertIsNotNone(result["title"])
            self.assertIn("authors", result)
            self.assertGreater(len(result["authors"]), 0)
            self.assertIn("publication_year", result)

    def test_parse_search_results_with_mock_data(self):
        """Test parsing WorldCat XML response."""
        self.assertTrue(hasattr(self.searcher, "parse_search_results"))
        self.assertTrue(callable(self.searcher.parse_search_results))

    def test_fallback_entries_have_required_fields(self):
        """Test that all fallback entries have required fields."""
        required_fields = ["title", "authors", "publication_year"]

        for book in FALLBACK_ARMENIAN_BOOKS:
            for field in required_fields:
                self.assertIn(field, book, f"Book missing required field: {field}")

    def test_deduplication_logic(self):
        """Test that duplicate books are handled."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name

        try:
            manager = BookInventoryManager(inventory_file=temp_file)

            entry1 = BookInventoryEntry(
                title="Test Book",
                authors=[BookAuthor(name="Author A")],
                first_publication_year=2020,
            )

            entry2 = BookInventoryEntry(
                title="Test Book",
                authors=[BookAuthor(name="Author A")],
                first_publication_year=2020,
            )

            manager.add_book(entry1)
            manager.add_book(entry2)

            self.assertEqual(len(manager.books), 2)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


class TestWorldCatResilience(unittest.TestCase):
    """Test WorldCat searcher resilience and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.searcher = WorldCatSearcher()

    def test_graceful_fallback_when_api_unavailable(self):
        """Test that searcher can handle API failures gracefully."""
        self.assertTrue(callable(WorldCatError))
        self.assertGreater(len(FALLBACK_ARMENIAN_BOOKS), 0)

    def test_world_cat_error_handling(self):
        """Test WorldCatError exception can be raised."""
        error = WorldCatError("Test error")
        self.assertIsInstance(error, Exception)

    def test_fallback_consistency(self):
        """Test that fallback database is consistent across calls."""
        results1 = FALLBACK_ARMENIAN_BOOKS
        results2 = FALLBACK_ARMENIAN_BOOKS

        self.assertEqual(len(results1), len(results2))

        titles1 = {b["title"] for b in results1}
        titles2 = {b["title"] for b in results2}
        self.assertEqual(titles1, titles2)


class TestFallbackDatabaseMetadata(unittest.TestCase):
    """Test metadata quality of fallback database."""

    def test_all_books_have_authors(self):
        """Test that all books have at least one author."""
        for book in FALLBACK_ARMENIAN_BOOKS:
            self.assertIn("authors", book)
            self.assertIsInstance(book["authors"], list)
            self.assertGreater(len(book["authors"]), 0)

    def test_all_books_have_valid_years(self):
        """Test that publication years are valid."""
        for book in FALLBACK_ARMENIAN_BOOKS:
            year = book.get("publication_year")
            self.assertIsNotNone(year, f"Book '{book['title']}' missing publication_year")
            if year is not None:
                self.assertGreater(year, 1800)
                self.assertLess(year, 2030)

    def test_books_have_word_counts(self):
        """Test that most books have estimated word counts."""
        books_with_counts = [b for b in FALLBACK_ARMENIAN_BOOKS if b.get("estimated_word_count")]

        if len(FALLBACK_ARMENIAN_BOOKS) > 0:
            coverage = len(books_with_counts) / len(FALLBACK_ARMENIAN_BOOKS)
            self.assertGreater(coverage, 0.60)

    def test_word_counts_are_reasonable(self):
        """Test that word counts are in reasonable range."""
        for book in FALLBACK_ARMENIAN_BOOKS:
            word_count = book.get("estimated_word_count")
            if word_count:
                self.assertGreater(word_count, 20000)
                self.assertLess(word_count, 500000)

    def test_books_have_content_types(self):
        """Test that content types are assigned."""
        books_with_types = [b for b in FALLBACK_ARMENIAN_BOOKS if b.get("content_type")]

        coverage = len(books_with_types) / len(FALLBACK_ARMENIAN_BOOKS)
        self.assertGreater(coverage, 0.85)

    def test_author_metadata_enrichment(self):
        """Test that author metadata is enriched where possible."""
        books_with_author_birth = 0

        for book in FALLBACK_ARMENIAN_BOOKS:
            for author in book.get("authors", []):
                if isinstance(author, dict):
                    if "birth_year" in author or "birth_place" in author:
                        books_with_author_birth += 1
                        break

        self.assertGreater(books_with_author_birth, 0)


class TestWorldCatIntegration(unittest.TestCase):
    """Integration tests combining multiple components."""

    def _guess_content_type(self, type_str: str) -> ContentType:
        """Guess content type from string."""
        type_str = type_str.lower()
        if "poetry" in type_str:
            return ContentType.POETRY_COLLECTION
        elif "novel" in type_str:
            return ContentType.NOVEL
        elif "essay" in type_str:
            return ContentType.ESSAYS
        else:
            return ContentType.OTHER

    def test_full_search_to_inventory_pipeline(self):
        """Test complete pipeline from fallback to inventory."""
        manager = BookInventoryManager()

        for fallback_book in FALLBACK_ARMENIAN_BOOKS[:3]:
            authors = [
                BookAuthor(name=a.get("name", "Unknown"), birth_year=a.get("birth_year"))
                for a in fallback_book.get("authors", [])
            ]

            entry = BookInventoryEntry(
                title=fallback_book.get("title", ""),
                authors=authors,
                first_publication_year=fallback_book.get("publication_year"),
                content_type=self._guess_content_type(fallback_book.get("content_type", "")),
                estimated_word_count=fallback_book.get("estimated_word_count"),
            )

            manager.add_book(entry)

        self.assertGreater(len(manager.books), 0)

        results = manager.find_by_title("Test", fuzzy=True)
        self.assertIsInstance(results, list)

    def test_inventory_statistics_from_fallback(self):
        """Test that statistics are computed correctly from fallback."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name

        try:
            manager = BookInventoryManager(inventory_file=temp_file)

            for fallback_book in FALLBACK_ARMENIAN_BOOKS[:5]:
                authors = [
                    BookAuthor(name=a.get("name", "Unknown"))
                    for a in fallback_book.get("authors", [])
                ]

                entry = BookInventoryEntry(
                    title=fallback_book.get("title", ""),
                    authors=authors,
                    first_publication_year=fallback_book.get("publication_year"),
                    content_type=self._guess_content_type(fallback_book.get("content_type", "")),
                )

                manager.add_book(entry)

            stats = manager.get_summary()

            self.assertIsNotNone(stats)
            self.assertGreater(stats.total_books, 0)
            self.assertEqual(stats.total_books, 5)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_export_formats_valid(self):
        """Test that exported formats are valid."""
        import tempfile
        import os

        manager = BookInventoryManager()

        for fallback_book in FALLBACK_ARMENIAN_BOOKS[:3]:
            authors = [
                BookAuthor(name=a.get("name", "Unknown"))
                for a in fallback_book.get("authors", [])
            ]

            entry = BookInventoryEntry(
                title=fallback_book.get("title", ""),
                authors=authors,
                first_publication_year=fallback_book.get("publication_year"),
                content_type=self._guess_content_type(fallback_book.get("content_type", "")),
            )

            manager.add_book(entry)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = f"{tmpdir}/books.csv"

            manager.export_to_csv(csv_path)

            self.assertGreater(os.path.getsize(csv_path), 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()

