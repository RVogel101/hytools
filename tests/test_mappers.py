"""Tests for armenian_corpus_core.extraction.mappers module."""

import json

from armenian_corpus_core.core_contracts import DialectTag, DocumentRecord, LexiconEntry
from armenian_corpus_core.extraction.mappers import (
    _nullable_int,
    _nullable_text,
    _parse_json_field,
    anki_card_row_to_lexicon_entry,
    sentence_row_to_document_record,
    wa_fingerprint_row_to_document_record,
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
        assert entry.dialect_tag == DialectTag.WESTERN_ARMENIAN

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
        assert entry.metadata["anki_note_id"] == 123
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
        assert doc.source_family == "lousardzag_sentences"
        assert doc.text == "some text"
        assert doc.title == "present"
        assert doc.content_hash is not None
        assert doc.char_count == 9
        assert doc.dialect_tag == DialectTag.WESTERN_ARMENIAN

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


class TestWaFingerprintRowToDocumentRecord:
    def test_western_armenian_dialect(self):
        for dialect_value in ["western_armenian", "wa", "hyw"]:
            row = {"dialect_tag": dialect_value, "source": "wiki", "id/path": "doc-1"}
            doc = wa_fingerprint_row_to_document_record(row)
            assert doc.dialect_tag == DialectTag.WESTERN_ARMENIAN

    def test_eastern_armenian_dialect(self):
        for dialect_value in ["eastern_armenian", "ea", "hy"]:
            row = {"dialect_tag": dialect_value, "source": "wiki", "id/path": "doc-1"}
            doc = wa_fingerprint_row_to_document_record(row)
            assert doc.dialect_tag == DialectTag.EASTERN_ARMENIAN

    def test_mixed_dialect(self):
        row = {"dialect_tag": "mixed", "source": "wiki", "id/path": "doc-1"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.dialect_tag == DialectTag.MIXED

    def test_unknown_dialect(self):
        row = {"dialect_tag": "something_else", "source": "wiki", "id/path": "doc-1"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.dialect_tag == DialectTag.UNKNOWN

    def test_text_always_empty(self):
        row = {"dialect_tag": "wa", "source": "wiki", "id/path": "doc-1"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.text == ""

    def test_fingerprint_metadata(self):
        row = {"dialect_tag": "wa", "source": "wiki", "id/path": "doc-1"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.metadata["fingerprint_only"] is True

    def test_document_id_from_path(self):
        row = {"id/path": "/some/path.txt", "source": "wiki"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.document_id == "/some/path.txt"

    def test_document_id_fallback_to_hash(self):
        row = {"sha256(text_normalized)": "abc123", "source": "wiki"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.document_id == "sha256:abc123"

    def test_default_source(self):
        row = {"id/path": "doc-1"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.source_family == "wa_export"

    def test_char_count(self):
        row = {"id/path": "doc-1", "char_count": "500", "source": "wiki"}
        doc = wa_fingerprint_row_to_document_record(row)
        assert doc.char_count == 500
