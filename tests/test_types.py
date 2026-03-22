"""Tests for core_contracts.types module."""

import pytest
from dataclasses import FrozenInstanceError

from hytool.core_contracts.types import (
    DialectTag,
    DocumentRecord,
    LexiconEntry,
    PhoneticResult,
)


class TestDialectTag:
    def test_values(self):
        assert DialectTag.WESTERN_ARMENIAN.value == "western_armenian"
        assert DialectTag.EASTERN_ARMENIAN.value == "eastern_armenian"
        assert DialectTag.MIXED.value == "mixed"
        assert DialectTag.UNKNOWN.value == "unknown"

    def test_is_str(self):
        assert isinstance(DialectTag.WESTERN_ARMENIAN, str)
        assert DialectTag.WESTERN_ARMENIAN == "western_armenian"

    def test_all_members(self):
        assert len(DialectTag) == 4


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
        assert doc.dialect_tag == DialectTag.UNKNOWN
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
            dialect_tag=DialectTag.WESTERN_ARMENIAN,
            metadata={"key": "value"},
        )
        assert doc.title == "Test Title"
        assert doc.dialect_tag == DialectTag.WESTERN_ARMENIAN
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
        assert entry.dialect_tag == DialectTag.WESTERN_ARMENIAN
        assert entry.metadata == {}

    def test_all_fields(self):
        entry = LexiconEntry(
            lemma="word",
            translation="translation",
            pos="noun",
            pronunciation="/wÉœËrd/",
            frequency_rank=42,
            syllable_count=1,
            dialect_tag=DialectTag.EASTERN_ARMENIAN,
            metadata={"source": "test"},
        )
        assert entry.frequency_rank == 42
        assert entry.dialect_tag == DialectTag.EASTERN_ARMENIAN

    def test_frozen(self):
        entry = LexiconEntry(lemma="test")
        with pytest.raises(FrozenInstanceError):
            entry.lemma = "other"  # type: ignore[attr-defined]


class TestPhoneticResult:
    def test_required_fields(self):
        result = PhoneticResult(
            word="test",
            ipa="/tÉ›st/",
            english_approx="test",
            max_phonetic_difficulty=1.5,
        )
        assert result.word == "test"
        assert result.ipa == "/tÉ›st/"
        assert result.max_phonetic_difficulty == 1.5

    def test_defaults(self):
        result = PhoneticResult(
            word="test",
            ipa="/tÉ›st/",
            english_approx="test",
            max_phonetic_difficulty=1.0,
        )
        assert result.metadata == {}

    def test_frozen(self):
        result = PhoneticResult(
            word="test",
            ipa="/tÉ›st/",
            english_approx="test",
            max_phonetic_difficulty=1.0,
        )
        with pytest.raises(FrozenInstanceError):
            result.word = "other"  # type: ignore[attr-defined]

