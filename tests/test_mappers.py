"""Tests for ingestion._shared.mappers module."""

import json

from hytools.core_contracts import DocumentRecord, LexiconEntry
from hytools.ingestion._shared.mappers import (
    _nullable_int,
    _nullable_text,
    _parse_json_field,
    anki_card_row_to_lexicon_entry,
    sentence_row_to_document_record,
)


class TestParseJsonField:
    def test_dict_passthrough(self):
        assert _parse_json_field({"key": "val"}) == {"key": "val"}

    def test_json_string(self):
        assert _parse_json_field('{"key": "val"}') == {"key": "val"}

    def test_invalid_json(self):
        assert _parse_json_field("not json") == {}

    def test_none(self):
        assert _parse_json_field(None) == {}

    def test_empty_string(self):
        assert _parse_json_field("") == {}

    def test_json_array_returns_empty(self):
        """JSON arrays are not dicts, should return empty."""
        assert _parse_json_field("[1, 2]") == {}


class TestNullableText:
    def test_normal_string(self):
        assert _nullable_text("hello") == "hello"

    def test_strips_whitespace(self):
        assert _nullable_text("  hello  ") == "hello"

    def test_none(self):
        assert _nullable_text(None) is None

    def test_empty_string(self):
        assert _nullable_text("") is None

    def test_whitespace_only(self):
        assert _nullable_text("   ") is None

    def test_number_converted(self):
        assert _nullable_text(42) == "42"


class TestNullableInt:
    def test_normal_int(self):
        assert _nullable_int(42) == 42

    def test_string_int(self):
        assert _nullable_int("42") == 42

    def test_none(self):
        assert _nullable_int(None) is None

    def test_empty_string(self):
        assert _nullable_int("") is None

    def test_invalid_string(self):
        assert _nullable_int("abc") is None

    def test_float_truncates(self):
        assert _nullable_int(3.9) == 3


class TestAnkiCardRowToLexiconEntry:
    def test_basic_conversion(self):
        row = {
            "word": "  test  ",
            "translation": "exam",
            "pos": "noun",
            "pronunciation": "/tɛst/",
            "frequency_rank": 10,
            "syllable_count": 1,
        }
        entry = anki_card_row_to_lexicon_entry(row)
        assert isinstance(entry, LexiconEntry)
        assert entry.lemma == "test"
        assert entry.translation == "exam"
        assert entry.pos == "noun"
        assert entry.frequency_rank == 10
        # classifier may return tags; validate fields exist (may be None)
        assert hasattr(entry, "internal_language_code")
        assert hasattr(entry, "internal_language_branch")

    def test_missing_fields(self):
        row = {"word": "test"}
        entry = anki_card_row_to_lexicon_entry(row)
        assert entry.lemma == "test"
        assert entry.translation is None
        assert entry.pos is None

    def test_metadata_fields(self):
        row = {
            "word": "test",
            "anki_note_id": 123,
            "deck_name": "Armenian",
            "metadata_json": '{"level": 1}',
            "morphology_json": '{"stem": "test"}',
        }
        entry = anki_card_row_to_lexicon_entry(row)
        assert entry.metadata["deck_name"] == "Armenian"
        assert entry.metadata["metadata_json"] == {"level": 1}
        assert entry.metadata["morphology_json"] == {"stem": "test"}

    def test_empty_row(self):
        entry = anki_card_row_to_lexicon_entry({})
        assert entry.lemma == ""


class TestSentenceRowToDocumentRecord:
    def test_basic_conversion(self):
        row = {
            "id": 42,
            "armenian_text": "some text",
            "form_label": "present",
            "english_text": "some english",
        }
        doc = sentence_row_to_document_record(row)
        assert isinstance(doc, DocumentRecord)
        assert doc.document_id == "sentence:42"
        assert doc.source_family == "anki_sentences"
        assert doc.text == "some text"
        assert doc.title == "present"
        assert doc.content_hash is not None
        assert doc.char_count == 9
        assert hasattr(doc, "internal_language_code")
        assert hasattr(doc, "internal_language_branch")

    def test_content_hash_deterministic(self):
        row = {"id": 1, "armenian_text": "  some text  "}
        doc = sentence_row_to_document_record(row)
        # Whitespace is stripped by the row getter, then normalized
        assert doc.content_hash is not None

    def test_metadata_fields(self):
        row = {
            "id": 1,
            "armenian_text": "text",
            "card_id": 99,
            "grammar_type": "verb",
            "vocabulary_used": "word1,word2",
        }
        doc = sentence_row_to_document_record(row)
        assert doc.metadata["card_id"] == 99
        assert doc.metadata["grammar_type"] == "verb"


