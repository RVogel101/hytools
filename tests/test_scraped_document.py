"""Tests for ScrapedDocument dataclass and insert_or_skip helper."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from hytools.ingestion._shared.scraped_document import (
    KNOWN_CONTENT_TYPES,
    KNOWN_DIALECT_LABELS,
    KNOWN_DIALECTS,
    KNOWN_INTERNAL_LANGUAGE_BRANCHES,
    KNOWN_INTERNAL_LANGUAGE_CODES,
    KNOWN_SOURCE_LANGUAGE_CODES,
    KNOWN_SOURCE_TYPES,
    KNOWN_WRITING_CATEGORIES,
    ScrapedDocument,
)


# ── ScrapedDocument construction ────────────────────────────────────────────

class TestScrapedDocumentConstruction:
    def test_minimal(self):
        doc = ScrapedDocument(source_family="wiki", text="hello")
        assert doc.source_family == "wiki"
        assert doc.text == "hello"
        assert doc.title is None
        assert doc.extra == {}

    def test_all_fields(self):
        doc = ScrapedDocument(
            source_family="archive_org",
            text="some text",
            title="My Book",
            source_url="https://example.com",
            author="Author",
            author_origin="lebanon",
            content_hash="abc123",
            source_language_code="hyw",
            internal_language_code="hy",
            internal_language_branch="hye-w",
            wa_score=0.95,
            publication_date="2024-01-01",
            original_date="1920-01-01",
            catalog_id="ia-1234",
            source_name="Internet Archive",
            collection="diaspora_books",
            source_type="archive",
            content_type="literature",
            writing_category="book",
            dialect="western_armenian",
            dialect_subcategory="western_lebanon",
            region="lebanon",
            confidence_region=0.9,
            dialect_label="likely_western",
            dialect_confidence=0.85,
            western_score=12.5,
            eastern_score=1.2,
            classical_score=3.0,
            extra={"custom_key": "value"},
        )
        assert doc.source_family == "archive_org"
        assert doc.author == "Author"
        assert doc.author_origin == "lebanon"
        assert doc.wa_score == 0.95
        assert doc.original_date == "1920-01-01"
        assert doc.source_name == "Internet Archive"
        assert doc.collection == "diaspora_books"
        assert doc.dialect == "western_armenian"
        assert doc.dialect_subcategory == "western_lebanon"
        assert doc.region == "lebanon"
        assert doc.confidence_region == 0.9
        assert doc.dialect_label == "likely_western"
        assert doc.dialect_confidence == 0.85
        assert doc.western_score == 12.5
        assert doc.eastern_score == 1.2
        assert doc.classical_score == 3.0
        assert doc.extra == {"custom_key": "value"}

    def test_extraction_date_auto_set(self):
        doc = ScrapedDocument(source_family="test", text="x")
        assert doc.extraction_date is not None
        assert "T" in doc.extraction_date  # ISO 8601 format

    def test_new_fields_default_none(self):
        doc = ScrapedDocument(source_family="test", text="x")
        assert doc.author_origin is None
        assert doc.original_date is None
        assert doc.source_name is None
        assert doc.collection is None
        assert doc.dialect is None
        assert doc.dialect_subcategory is None
        assert doc.region is None
        assert doc.confidence_region is None
        assert doc.dialect_label is None
        assert doc.dialect_confidence is None
        assert doc.western_score is None
        assert doc.eastern_score is None
        assert doc.classical_score is None
        # Quantitative fields
        assert doc.char_count is None
        assert doc.word_count is None
        assert doc.sentence_count is None
        assert doc.ttr is None
        assert doc.sttr is None
        assert doc.yule_k is None
        assert doc.unique_words is None
        assert doc.avg_sentence_length is None
        assert doc.flesch_kincaid_grade is None
        assert doc.entropy is None
        assert doc.classical_markers_count is None
        assert doc.reformed_markers_count is None
        assert doc.classical_to_reformed_ratio is None
        assert doc.code_switching_index is None
        assert doc.dialect_purity_score is None


# ── to_insert_dict ──────────────────────────────────────────────────────────

class TestToInsertDict:
    def test_basic_structure(self):
        doc = ScrapedDocument(
            source_family="wiki",
            text="hello world",
            title="Test",
            source_url="https://example.com",
        )
        d = doc.to_insert_dict()
        assert d["source"] == "wiki"
        assert d["title"] == "Test"
        assert d["text"] == "hello world"
        assert d["url"] == "https://example.com"
        assert d["author"] is None
        assert isinstance(d["metadata"], dict)

    def test_metadata_contains_promoted_fields(self):
        doc = ScrapedDocument(
            source_family="test",
            text="x",
            source_language_code="hyw",
            wa_score=0.8,
            source_type="archive",
            publication_date="2024-01-01",
            catalog_id="id-123",
            # New fields
            dialect="western_armenian",
            dialect_subcategory="western_lebanon",
            region="lebanon",
            dialect_label="likely_western",
            western_score=10.0,
            char_count=100,
            word_count=20,
            ttr=0.85,
            entropy=5.2,
        )
        d = doc.to_insert_dict()
        meta = d["metadata"]
        assert meta["source_language_code"] == "hyw"
        assert meta["wa_score"] == 0.8
        assert meta["source_type"] == "archive"
        assert meta["publication_date"] == "2024-01-01"
        assert meta["catalog_id"] == "id-123"
        assert meta["dialect"] == "western_armenian"
        assert meta["dialect_subcategory"] == "western_lebanon"
        assert meta["region"] == "lebanon"
        assert meta["dialect_label"] == "likely_western"
        assert meta["western_score"] == 10.0
        assert meta["char_count"] == 100
        assert meta["word_count"] == 20
        assert meta["ttr"] == 0.85
        assert meta["entropy"] == 5.2

    def test_none_fields_excluded_from_metadata(self):
        doc = ScrapedDocument(source_family="test", text="x")
        d = doc.to_insert_dict()
        meta = d["metadata"]
        assert "source_language_code" not in meta
        assert "wa_score" not in meta
        assert "catalog_id" not in meta

    def test_extra_merged_into_metadata(self):
        doc = ScrapedDocument(
            source_family="test",
            text="x",
            source_type="news",
            extra={"custom": "value", "tags": ["a", "b"]},
        )
        d = doc.to_insert_dict()
        meta = d["metadata"]
        assert meta["custom"] == "value"
        assert meta["tags"] == ["a", "b"]
        assert meta["source_type"] == "news"

    def test_extraction_date_in_metadata(self):
        doc = ScrapedDocument(source_family="test", text="x")
        d = doc.to_insert_dict()
        assert "extraction_date" in d["metadata"]


# ── to_document_record ──────────────────────────────────────────────────────

class TestToDocumentRecord:
    def test_conversion(self):
        doc = ScrapedDocument(
            source_family="wiki",
            text="hello",
            title="Test",
            source_url="https://example.com",
            content_hash="abc123",
            internal_language_code="hy",
            internal_language_branch="hye-w",
            extra={"custom": "val"},
        )
        record = doc.to_document_record()
        assert record.source_family == "wiki"
        assert record.text == "hello"
        assert record.title == "Test"
        assert record.source_url == "https://example.com"
        assert record.content_hash == "abc123"
        assert record.char_count == 5
        assert record.internal_language_code == "hy"
        assert record.internal_language_branch == "hye-w"
        assert record.metadata == {"custom": "val"}

    def test_empty_hash_defaults(self):
        doc = ScrapedDocument(source_family="test", text="x")
        record = doc.to_document_record()
        assert record.document_id == ""
        assert record.content_hash is None


# ── validate ────────────────────────────────────────────────────────────────

class TestValidate:
    def test_valid_document(self):
        doc = ScrapedDocument(
            source_family="wiki",
            text="some text",
            source_language_code="hyw",
            internal_language_code="hy",
            internal_language_branch="hye-w",
            wa_score=0.8,
        )
        assert doc.validate() == []

    def test_empty_text(self):
        doc = ScrapedDocument(source_family="wiki", text="")
        warnings = doc.validate()
        assert "empty text" in warnings

    def test_whitespace_only_text(self):
        doc = ScrapedDocument(source_family="wiki", text="   ")
        assert "empty text" in doc.validate()

    def test_empty_source_family(self):
        doc = ScrapedDocument(source_family="", text="x")
        assert "empty source_family" in doc.validate()

    def test_unknown_source_language_code(self):
        doc = ScrapedDocument(source_family="test", text="x", source_language_code="zz")
        warnings = doc.validate()
        assert any("unknown source_language_code" in w for w in warnings)

    def test_unknown_internal_language_code(self):
        doc = ScrapedDocument(source_family="test", text="x", internal_language_code="xx")
        warnings = doc.validate()
        assert any("unknown internal_language_code" in w for w in warnings)

    def test_unknown_internal_language_branch(self):
        doc = ScrapedDocument(source_family="test", text="x", internal_language_branch="bad")
        warnings = doc.validate()
        assert any("unknown internal_language_branch" in w for w in warnings)

    def test_wa_score_out_of_range_high(self):
        doc = ScrapedDocument(source_family="test", text="x", wa_score=1.5)
        assert any("wa_score out of range" in w for w in doc.validate())

    def test_wa_score_out_of_range_low(self):
        doc = ScrapedDocument(source_family="test", text="x", wa_score=-0.1)
        assert any("wa_score out of range" in w for w in doc.validate())

    def test_wa_score_boundary_valid(self):
        for score in (0.0, 0.5, 1.0):
            doc = ScrapedDocument(source_family="test", text="x", wa_score=score)
            assert not any("wa_score" in w for w in doc.validate())

    def test_known_codes(self):
        assert "hyw" in KNOWN_SOURCE_LANGUAGE_CODES
        assert "hye" in KNOWN_SOURCE_LANGUAGE_CODES
        assert "hy" in KNOWN_INTERNAL_LANGUAGE_CODES
        assert "hye-w" in KNOWN_INTERNAL_LANGUAGE_BRANCHES


# ── insert_or_skip ──────────────────────────────────────────────────────────

class TestInsertOrSkip:
    def _make_mock_client(self, raises=None):
        client = MagicMock()
        if raises:
            client.insert_document.side_effect = raises
        else:
            client.insert_document.return_value = "fake_id"
        return client

    def test_legacy_call_inserts(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        result = insert_or_skip(
            client,
            source="wiki",
            title="Test",
            text="hello",
            url="https://example.com",
            metadata={"source_type": "encyclopedia"},
            config={},
        )
        assert result is True
        client.insert_document.assert_called_once()
        call_kwargs = client.insert_document.call_args
        assert call_kwargs[1]["source"] == "wiki"
        assert call_kwargs[1]["title"] == "Test"
        assert call_kwargs[1]["text"] == "hello"

    def test_legacy_call_skips_duplicate(self):
        from hytools.ingestion._shared.helpers import insert_or_skip
        try:
            from pymongo.errors import DuplicateKeyError
        except ImportError:
            DuplicateKeyError = Exception

        client = self._make_mock_client(raises=DuplicateKeyError("dup"))
        result = insert_or_skip(client, source="wiki", title="t", text="x")
        assert result is False

    def test_doc_param_inserts(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        doc = ScrapedDocument(
            source_family="archive_org",
            text="content",
            title="Book",
            source_url="https://archive.org/details/123",
            source_type="book",
        )
        result = insert_or_skip(client, doc=doc, config={})
        assert result is True
        client.insert_document.assert_called_once()
        kwargs = client.insert_document.call_args[1]
        assert kwargs["source"] == "archive_org"
        assert kwargs["text"] == "content"
        assert kwargs["title"] == "Book"
        assert kwargs["url"] == "https://archive.org/details/123"
        assert kwargs["metadata"]["source_type"] == "book"

    def test_doc_param_skips_duplicate(self):
        from hytools.ingestion._shared.helpers import insert_or_skip
        try:
            from pymongo.errors import DuplicateKeyError
        except ImportError:
            DuplicateKeyError = Exception

        client = self._make_mock_client(raises=DuplicateKeyError("dup"))
        doc = ScrapedDocument(source_family="test", text="x")
        result = insert_or_skip(client, doc=doc)
        assert result is False

    def test_doc_with_author(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        doc = ScrapedDocument(
            source_family="dpla",
            text="content",
            author="John Doe",
        )
        insert_or_skip(client, doc=doc)
        kwargs = client.insert_document.call_args[1]
        assert kwargs["author"] == "John Doe"

    def test_legacy_with_author(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        insert_or_skip(client, source="dpla", text="x", author="Jane")
        kwargs = client.insert_document.call_args[1]
        assert kwargs["author"] == "Jane"

    def test_validation_warnings_logged(self):
        """Validation warnings are logged but insert proceeds."""
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        doc = ScrapedDocument(
            source_family="test",
            text="x",
            wa_score=5.0,  # out of range
        )
        result = insert_or_skip(client, doc=doc)
        assert result is True  # still inserts despite validation warning
        client.insert_document.assert_called_once()


# ── Known constants ─────────────────────────────────────────────────────────

class TestKnownConstants:
    def test_known_dialect_labels(self):
        assert "likely_western" in KNOWN_DIALECT_LABELS
        assert "likely_eastern" in KNOWN_DIALECT_LABELS
        assert "inconclusive" in KNOWN_DIALECT_LABELS

    def test_known_dialects(self):
        assert "western_armenian" in KNOWN_DIALECTS
        assert "eastern_armenian" in KNOWN_DIALECTS
        assert "classical_armenian" in KNOWN_DIALECTS

    def test_known_source_types(self):
        assert "encyclopedia" in KNOWN_SOURCE_TYPES
        assert "newspaper" in KNOWN_SOURCE_TYPES
        assert "archive" in KNOWN_SOURCE_TYPES

    def test_known_content_types(self):
        assert "article" in KNOWN_CONTENT_TYPES
        assert "literature" in KNOWN_CONTENT_TYPES
        assert "poem" in KNOWN_CONTENT_TYPES

    def test_known_writing_categories(self):
        assert "book" in KNOWN_WRITING_CATEGORIES
        assert "fiction" in KNOWN_WRITING_CATEGORIES
        assert "news" in KNOWN_WRITING_CATEGORIES


# ── validate (new fields) ──────────────────────────────────────────────────

class TestValidateNewFields:
    def test_unknown_dialect_label(self):
        doc = ScrapedDocument(source_family="test", text="x", dialect_label="bad_label")
        assert any("unknown dialect_label" in w for w in doc.validate())

    def test_known_dialect_label_ok(self):
        doc = ScrapedDocument(source_family="test", text="x", dialect_label="likely_western")
        assert not any("dialect_label" in w for w in doc.validate())

    def test_unknown_dialect(self):
        doc = ScrapedDocument(source_family="test", text="x", dialect="imaginary")
        assert any("unknown dialect" in w for w in doc.validate())

    def test_known_dialect_ok(self):
        doc = ScrapedDocument(source_family="test", text="x", dialect="western_armenian")
        assert not any("unknown dialect" in w for w in doc.validate())

    def test_unknown_source_type(self):
        doc = ScrapedDocument(source_family="test", text="x", source_type="magic")
        assert any("unknown source_type" in w for w in doc.validate())

    def test_known_source_type_ok(self):
        doc = ScrapedDocument(source_family="test", text="x", source_type="newspaper")
        assert not any("source_type" in w for w in doc.validate())

    def test_unknown_content_type(self):
        doc = ScrapedDocument(source_family="test", text="x", content_type="video")
        assert any("unknown content_type" in w for w in doc.validate())

    def test_unknown_writing_category(self):
        doc = ScrapedDocument(source_family="test", text="x", writing_category="zz")
        assert any("unknown writing_category" in w for w in doc.validate())

    def test_confidence_region_out_of_range(self):
        doc = ScrapedDocument(source_family="test", text="x", confidence_region=1.5)
        assert any("confidence_region out of range" in w for w in doc.validate())

    def test_confidence_region_valid(self):
        doc = ScrapedDocument(source_family="test", text="x", confidence_region=0.9)
        assert not any("confidence_region" in w for w in doc.validate())


# ── compute_standard_linguistics ────────────────────────────────────────────

class TestComputeStandardLinguistics:
    def test_basic_counts(self):
        doc = ScrapedDocument(source_family="test", text="hello world foo bar baz")
        doc.compute_standard_linguistics()
        assert doc.char_count == len("hello world foo bar baz")
        assert doc.word_count is not None
        assert doc.word_count > 0

    def test_empty_text_noop(self):
        doc = ScrapedDocument(source_family="test", text="")
        doc.compute_standard_linguistics()
        assert doc.char_count is None
        assert doc.word_count is None

    def test_whitespace_only_noop(self):
        doc = ScrapedDocument(source_family="test", text="   ")
        doc.compute_standard_linguistics()
        assert doc.char_count is None

    def test_ttr_computed(self):
        doc = ScrapedDocument(source_family="test", text="one two three four five six seven eight nine ten")
        doc.compute_standard_linguistics()
        assert doc.ttr is not None
        assert 0.0 <= doc.ttr <= 1.0

    def test_entropy_computed(self):
        doc = ScrapedDocument(source_family="test", text="word word word other other third")
        doc.compute_standard_linguistics()
        assert doc.entropy is not None
        assert doc.entropy > 0.0

    def test_sentence_count(self):
        doc = ScrapedDocument(source_family="test", text="First sentence! Second sentence? Third one:")
        doc.compute_standard_linguistics()
        assert doc.sentence_count is not None
        assert doc.sentence_count >= 3

    def test_avg_sentence_length(self):
        doc = ScrapedDocument(source_family="test", text="First sentence here! Short one?")
        doc.compute_standard_linguistics()
        assert doc.avg_sentence_length is not None
        assert doc.avg_sentence_length > 0

    def test_unique_words(self):
        doc = ScrapedDocument(source_family="test", text="the the the cat cat dog")
        doc.compute_standard_linguistics()
        assert doc.unique_words is not None
        assert doc.unique_words <= doc.word_count

    def test_yule_k_computed(self):
        doc = ScrapedDocument(source_family="test", text="cat dog fox hen owl cat dog fox hen owl")
        doc.compute_standard_linguistics()
        assert doc.yule_k is not None

    def test_code_switching_index_zero_for_english(self):
        doc = ScrapedDocument(source_family="test", text="this is english text only")
        doc.compute_standard_linguistics()
        assert doc.code_switching_index == 0.0
        assert doc.dialect_purity_score == 1.0

    def test_classical_markers_count(self):
        # իւ is a classical marker
        doc = ScrapedDocument(source_family="test", text="\u056B\u0582 \u056B\u0582 \u056B\u0582")
        doc.compute_standard_linguistics()
        assert doc.classical_markers_count is not None
        assert doc.classical_markers_count >= 3

    def test_sttr_computed(self):
        # Generate enough words for STTR (needs 100+)
        words = [f"word{i}" for i in range(150)]
        doc = ScrapedDocument(source_family="test", text=" ".join(words))
        doc.compute_standard_linguistics()
        assert doc.sttr is not None
        assert 0.0 <= doc.sttr <= 1.0

    def test_flesch_kincaid_computed(self):
        doc = ScrapedDocument(source_family="test", text="First sentence here! Second one here?")
        doc.compute_standard_linguistics()
        assert doc.flesch_kincaid_grade is not None

    def test_metrics_in_to_insert_dict_after_compute(self):
        doc = ScrapedDocument(source_family="test", text="hello world foo bar baz")
        doc.compute_standard_linguistics()
        d = doc.to_insert_dict()
        meta = d["metadata"]
        assert "char_count" in meta
        assert "word_count" in meta
        assert "ttr" in meta
        assert "entropy" in meta


# ── insert_or_skip auto-computes linguistics ────────────────────────────────

class TestInsertOrSkipAutoCompute:
    def _make_mock_client(self):
        client = MagicMock()
        client.insert_document.return_value = "fake_id"
        return client

    def test_auto_computes_on_insert(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        doc = ScrapedDocument(source_family="test", text="hello world foo bar baz")
        assert doc.char_count is None  # not yet computed
        insert_or_skip(client, doc=doc)
        assert doc.char_count is not None
        assert doc.word_count is not None

    def test_skips_compute_if_already_done(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        doc = ScrapedDocument(source_family="test", text="hello world", char_count=999)
        insert_or_skip(client, doc=doc)
        assert doc.char_count == 999  # not overwritten

    def test_computed_metrics_in_metadata(self):
        from hytools.ingestion._shared.helpers import insert_or_skip

        client = self._make_mock_client()
        doc = ScrapedDocument(source_family="test", text="hello world foo bar baz qux")
        insert_or_skip(client, doc=doc)
        kwargs = client.insert_document.call_args[1]
        meta = kwargs["metadata"]
        assert "char_count" in meta
        assert "word_count" in meta
        assert "entropy" in meta
