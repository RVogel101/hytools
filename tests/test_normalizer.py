"""Tests for hytools.cleaning.normalizer."""

import pytest

from hytools.cleaning.normalizer import (
    normalize_unicode,
    normalize_whitespace,
    remove_junk_lines,
    remove_foreign_fragments,
    normalize,
)


class TestNormalizeUnicode:
    def test_nfc_applied(self):
        # Composed vs decomposed 'é'
        import unicodedata
        decomposed = "e\u0301"
        result = normalize_unicode(decomposed)
        assert result == unicodedata.normalize("NFC", decomposed)

    def test_armenian_unchanged(self):
        text = "\u0561\u0562\u0563"
        assert normalize_unicode(text) == text


class TestNormalizeWhitespace:
    def test_multiple_spaces(self):
        text = "hello    world"
        result = normalize_whitespace(text)
        assert result == "hello world"

    def test_tabs_replaced(self):
        text = "hello\tworld"
        result = normalize_whitespace(text)
        assert result == "hello world"

    def test_trailing_spaces_stripped(self):
        text = "hello   "
        result = normalize_whitespace(text)
        assert result == "hello"

    def test_newlines_preserved(self):
        text = "line1\nline2"
        result = normalize_whitespace(text)
        assert "\n" in result


class TestRemoveJunkLines:
    def test_junk_line_removed(self):
        text = "good line\n***\nanother good line"
        result = remove_junk_lines(text)
        assert "***" not in result

    def test_normal_text_kept(self):
        text = "Hello World\nGoodbye"
        result = remove_junk_lines(text)
        assert "Hello World" in result
        assert "Goodbye" in result

    def test_empty_lines_preserved(self):
        text = "line1\n\nline2"
        result = remove_junk_lines(text)
        assert "line1" in result
        assert "line2" in result


class TestRemoveForeignFragments:
    def test_english_removed(self):
        text = "\u0561\u0562\u0563 Hello \u0564\u0565\u0566"
        result = remove_foreign_fragments(text)
        assert "Hello" not in result

    def test_parenthesized_foreign(self):
        text = "\u0561\u0562 (English text) \u0563\u0564"
        result = remove_foreign_fragments(text)
        assert "English" not in result

    def test_armenian_kept(self):
        text = "\u0561\u0562\u0563"
        result = remove_foreign_fragments(text)
        assert "\u0561\u0562\u0563" in result

    def test_quoted_foreign(self):
        text = "\u0561\u0562 \u00abforeign text\u00bb \u0563\u0564"
        result = remove_foreign_fragments(text)
        assert "foreign" not in result


class TestNormalize:
    def test_full_pipeline(self):
        text = "  \u0561\u0562\u0563   Hello  \n***\n\u0564\u0565\u0566  "
        result = normalize(text)
        assert isinstance(result, str)
        # Foreign removed, junk lines removed, whitespace normalized
        assert "Hello" not in result
        assert "***" not in result
        assert "\u0561\u0562\u0563" in result

    def test_empty_string(self):
        assert normalize("") == ""

    def test_only_armenian(self):
        text = "\u0561\u0562\u0563 \u0564\u0565\u0566"
        result = normalize(text)
        assert "\u0561" in result
