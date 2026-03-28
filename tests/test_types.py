"""Tests for core_contracts.types module."""

import pytest
from dataclasses import FrozenInstanceError

from hytools.core_contracts.types import (
    DocumentRecord,
    LexiconEntry,
    PhoneticResult,
)


# DialectTag removed — use internal_language_code and internal_language_branch on records.


class TestDocumentRecord:
    def test_required_fields(self):
        doc = DocumentRecord(
            document_id="test-1",
            source_family="test_source",
            text="sample text",
        )
        assert doc.document_id == "test-1"
        assert doc.source_family == "test_source"
        assert doc.text == "sample text"

    def test_defaults(self):
        doc = DocumentRecord(
            document_id="test-1",
            source_family="test_source",
            text="sample text",
        )
        assert doc.title is None
        assert doc.source_url is None
        assert doc.content_hash is None
        assert doc.char_count is None
        assert doc.internal_language_code is None
        assert doc.internal_language_branch is None
        assert doc.metadata == {}

    def test_all_fields(self):
        doc = DocumentRecord(
            document_id="test-1",
            source_family="anki_sentences",
            text="sample text",
            title="Test Title",
            source_url="http://example.com",
            content_hash="abc123",
            char_count=11,
            internal_language_code="hyw",
            internal_language_branch="hye-w",
            metadata={"key": "value"},
        )
        assert doc.title == "Test Title"
        assert doc.internal_language_code == "hyw"
        assert doc.internal_language_branch == "hye-w"
        assert doc.metadata == {"key": "value"}

    def test_frozen(self):
        doc = DocumentRecord(
            document_id="test-1",
            source_family="test_source",
            text="sample text",
        )
        with pytest.raises(FrozenInstanceError):
            doc.text = "new text"  # type: ignore[attr-defined]

    def test_equality(self):
        kwargs = dict(document_id="test-1", source_family="test", text="hello")
        assert DocumentRecord(**kwargs) == DocumentRecord(**kwargs)  # type: ignore[arg-type]

    def test_metadata_default_not_shared(self):
        """Each instance should get its own empty dict, not a shared one."""
        doc1 = DocumentRecord(document_id="a", source_family="s", text="t")
        doc2 = DocumentRecord(document_id="b", source_family="s", text="t")
        assert doc1.metadata is not doc2.metadata


class TestLexiconEntry:
    def test_required_fields(self):
        entry = LexiconEntry(lemma="test")
        assert entry.lemma == "test"

    def test_defaults(self):
        entry = LexiconEntry(lemma="test")
        assert entry.translation is None
        assert entry.pos is None
        assert entry.pronunciation is None
        assert entry.frequency_rank is None
        assert entry.syllable_count is None
        assert entry.internal_language_code is None
        assert entry.internal_language_branch is None
        assert entry.metadata == {}

    def test_all_fields(self):
        entry = LexiconEntry(
            lemma="word",
            translation="translation",
            pos="noun",
            pronunciation="/wɜːrd/",
            frequency_rank=42,
            syllable_count=1,
            internal_language_code="hye",
            internal_language_branch="hye-e",
            metadata={"source": "test"},
        )
        assert entry.frequency_rank == 42
        assert entry.internal_language_code == "hye"
        assert entry.internal_language_branch == "hye-e"

    def test_frozen(self):
        entry = LexiconEntry(lemma="test")
        with pytest.raises(FrozenInstanceError):
            entry.lemma = "other"  # type: ignore[attr-defined]


class TestPhoneticResult:
    def test_required_fields(self):
        result = PhoneticResult(
            word="test",
            ipa="/tɛst/",
            english_approx="test",
            max_phonetic_difficulty=1.5,
        )
        assert result.word == "test"
        assert result.ipa == "/tɛst/"
        assert result.max_phonetic_difficulty == 1.5

    def test_defaults(self):
        result = PhoneticResult(
            word="test",
            ipa="/tɛst/",
            english_approx="test",
            max_phonetic_difficulty=1.0,
        )
        assert result.metadata == {}

    def test_frozen(self):
        result = PhoneticResult(
            word="test",
            ipa="/tɛst/",
            english_approx="test",
            max_phonetic_difficulty=1.0,
        )
        with pytest.raises(FrozenInstanceError):
            result.word = "other"  # type: ignore[attr-defined]
