"""Tests for core_contracts.hashing module."""

import hashlib
import unicodedata

from hytools.core_contracts.hashing import (
    normalize_text_for_hash,
    sha256_normalized,
)


class TestNormalizeTextForHash:
    def test_basic_text(self):
        assert normalize_text_for_hash("hello world") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_text_for_hash("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert normalize_text_for_hash("  hello  ") == "hello"

    def test_tabs_and_newlines(self):
        assert normalize_text_for_hash("hello\t\n  world") == "hello world"

    def test_nfkc_normalization(self):
        # NFKC decomposes compatibility characters
        # U+FB01 LATIN SMALL LIGATURE FI → fi
        assert normalize_text_for_hash("\ufb01") == "fi"

    def test_armenian_text(self):
        text = "  \u0540\u0561\u0575\u0565\u0580\u0565\u0576  "
        result = normalize_text_for_hash(text)
        assert result == "\u0540\u0561\u0575\u0565\u0580\u0565\u0576"

    def test_empty_string(self):
        assert normalize_text_for_hash("") == ""

    def test_only_whitespace(self):
        assert normalize_text_for_hash("   \t\n  ") == ""

    def test_idempotent(self):
        text = "  hello   world  "
        first = normalize_text_for_hash(text)
        second = normalize_text_for_hash(first)
        assert first == second


class TestSha256Normalized:
    def test_deterministic(self):
        h1 = sha256_normalized("hello world")
        h2 = sha256_normalized("hello world")
        assert h1 == h2

    def test_whitespace_invariant(self):
        """Different whitespace should produce the same hash."""
        h1 = sha256_normalized("hello world")
        h2 = sha256_normalized("hello   world")
        h3 = sha256_normalized("  hello\tworld  ")
        assert h1 == h2 == h3

    def test_returns_hex_string(self):
        result = sha256_normalized("test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_manual_hash(self):
        text = "hello world"
        normalized = unicodedata.normalize("NFKC", text)
        expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        assert sha256_normalized(text) == expected

    def test_empty_string(self):
        result = sha256_normalized("")
        assert len(result) == 64

    def test_different_text_different_hash(self):
        assert sha256_normalized("hello") != sha256_normalized("world")
