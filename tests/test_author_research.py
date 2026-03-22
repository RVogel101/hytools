"""Tests for author research and profiling system (moved from WesternArmenianLLM).

Tests cover:
- AuthorProfile creation and validation
- Author name searching and matching
- Profile timeline generation
- Bibliography management
- Export formats (CSV, JSONL, JSON)
"""

import json
import tempfile
import unittest
from pathlib import Path

from hytools.ingestion.discovery.author_research import (
    AuthorChronology,
    AuthorProfile,
    AuthorProfileManager,
)


class TestAuthorProfile(unittest.TestCase):
    """Test AuthorProfile dataclass."""

    def test_create_basic_profile(self):
        """Test creating a basic author profile."""
        profile = AuthorProfile(
            author_id="test001",
            primary_name="Օ. Թունեան",
        )

        self.assertEqual(profile.author_id, "test001")
        self.assertEqual(profile.primary_name, "Օ. Թունեան")

    def test_profile_with_full_metadata(self):
        """Test creating profile with complete metadata."""
        profile = AuthorProfile(
            author_id="tunean1880",
            primary_name="Օ. Թունեան",
            name_variants=["O. Tunean", "Oshin Tunean"],
            birth_year=1880,
            birth_place="Adana",
            death_year=1968,
            writing_period_start=1905,
            writing_period_end=1965,
            genres=["poetry", "essay"],
            topics=["diaspora", "identity"],
            known_works_count=15,
            corpus_coverage_percentage=75.0,
            flags=["canonical"],
        )

        self.assertEqual(profile.birth_year, 1880)
        self.assertEqual(profile.writing_period_end, 1965)
        self.assertTrue(profile.is_canonical)

    def test_writing_duration_calculation(self):
        """Test that writing duration is calculated correctly."""
        profile = AuthorProfile(
            author_id="test001",
            primary_name="Test Author",
            writing_period_start=1900,
            writing_period_end=1920,
        )

        self.assertEqual(profile.writing_duration, 20)

    def test_writing_duration_missing_dates(self):
        """Test that writing duration returns None if dates missing."""
        profile = AuthorProfile(
            author_id="test001",
            primary_name="Test Author",
        )

        self.assertIsNone(profile.writing_duration)

    def test_profile_to_dict(self):
        """Test converting profile to dictionary."""
        profile = AuthorProfile(
            author_id="test001",
            primary_name="Test Author",
            birth_year=1880,
        )

        profile_dict = profile.to_dict()

        self.assertIsInstance(profile_dict, dict)
        self.assertEqual(profile_dict["author_id"], "test001")
        self.assertEqual(profile_dict["birth_year"], 1880)


class TestAuthorProfileManager(unittest.TestCase):
    """Test AuthorProfileManager operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profiles_file = f"{self.temp_dir.name}/test_profiles.jsonl"
        self.manager = AuthorProfileManager(profiles_file=self.profiles_file)

    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()

    def test_manager_initializes(self):
        """Test that manager initializes successfully."""
        self.assertIsNotNone(self.manager)
        self.assertEqual(len(self.manager.profiles), 0)

    def test_add_and_retrieve_profile(self):
        """Test adding and retrieving profiles."""
        profile = AuthorProfile(
            author_id="test001",
            primary_name="Test Author",
        )

        self.manager.add_profile(profile)

        self.assertEqual(len(self.manager.profiles), 1)
        self.assertIn("test001", self.manager.profiles)

    def test_find_by_name_exact_match(self):
        """Test finding author by exact name match."""
        profile = AuthorProfile(
            author_id="test001",
            primary_name="Test Author",
        )

        self.manager.add_profile(profile)
        results = self.manager.find_by_name("Test Author", fuzzy=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].author_id, "test001")

    def test_save_and_load_profiles(self):
        """Test saving and loading profiles via MongoDB (mocked)."""
        from unittest.mock import MagicMock, patch

        profile = AuthorProfile(
            author_id="test001",
            primary_name="Test Author",
            birth_year=1880,
        )
        stored = []

        def fake_save(docs):
            stored.clear()
            stored.extend(docs)
            return len(docs)

        def fake_load():
            return list(stored)

        fake_client = MagicMock()
        fake_client.save_author_profiles = fake_save
        fake_client.load_author_profiles = fake_load

        config = {"database": {"mongodb_uri": "mongodb://localhost:27017/"}}
        manager_with_mongo = AuthorProfileManager(profiles_file=self.profiles_file, config=config)
        manager_with_mongo.add_profile(profile)

        with patch("ingestion._shared.helpers.open_mongodb_client") as open_mongo:
            open_mongo.return_value.__enter__.return_value = fake_client
            open_mongo.return_value.__exit__.return_value = None
            manager_with_mongo.save_profiles()
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["author_id"], "test001")

        with patch("ingestion._shared.helpers.open_mongodb_client") as open_mongo:
            open_mongo.return_value.__enter__.return_value = fake_client
            open_mongo.return_value.__exit__.return_value = None
            new_manager = AuthorProfileManager(profiles_file=self.profiles_file, config=config)

        self.assertEqual(len(new_manager.profiles), 1)
        self.assertIn("test001", new_manager.profiles)


class TestAuthorChronology(unittest.TestCase):
    """Test AuthorChronology dataclass."""

    def test_create_chronology_entry(self):
        """Test creating a chronology entry."""
        entry = AuthorChronology(
            year=1880,
            event_type="birth",
            description="Born in Adana",
            work_title=None,
        )

        self.assertEqual(entry.year, 1880)
        self.assertEqual(entry.event_type, "birth")


if __name__ == "__main__":
    unittest.main()
