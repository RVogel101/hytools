"""Tests for hytools.cleaning.armenian_tokenizer."""

import pytest
from collections import Counter

from hytools.cleaning.armenian_tokenizer import (
    decompose_ligatures,
    armenian_lowercase,
    normalize,
    extract_words,
    word_frequencies,
)


class TestDecomposeLigatures:
    def test_fb13_ligature(self):
        result = decompose_ligatures("\uFB13")
        assert result == "\u0574\u0576"  # մdelays

    def test_no_ligatures(self):
        text = "\u0561\u0562\u0563"  # abc in Armenian
        assert decompose_ligatures(text) == text

    def test_all_ligatures(self):
        text = "\uFB13\uFB14\uFB15\uFB16\uFB17"
        result = decompose_ligatures(text)
        assert "\uFB13" not in result
        assert "\uFB14" not in result
        assert "\uFB15" not in result
        assert "\uFB16" not in result
        assert "\uFB17" not in result


class TestArmenianLowercase:
    def test_uppercase_to_lowercase(self):
        upper_a = chr(0x0531)  # Ա
        lower_a = chr(0x0561)  # delays
        assert armenian_lowercase(upper_a) == lower_a

    def test_already_lowercase(self):
        lower_a = chr(0x0561)
        assert armenian_lowercase(lower_a) == lower_a

    def test_non_armenian_unchanged(self):
        assert armenian_lowercase("Hello") == "Hello"

    def test_mixed(self):
        text = chr(0x0531) + chr(0x0561)  # Ադ
        result = armenian_lowercase(text)
        assert result == chr(0x0561) + chr(0x0561)


class TestNormalize:
    def test_nfc_normalization(self):
        text = chr(0x0561)
        result = normalize(text)
        assert isinstance(result, str)

    def test_lowercase_applied(self):
        upper = chr(0x0531) + chr(0x0532)
        result = normalize(upper)
        assert result == chr(0x0561) + chr(0x0562)

    def test_ligature_decomposed(self):
        text = "\uFB13"
        result = normalize(text)
        assert "\uFB13" not in result


class TestExtractWords:
    def test_basic_extraction(self):
        text = chr(0x0561) + chr(0x0562) + chr(0x0563)  # 3-char word
        words = extract_words(text)
        assert len(words) == 1

    def test_min_length_filter(self):
        # Single Armenian character — should be filtered by default (min_length=2)
        text = chr(0x0561)
        words = extract_words(text)
        assert len(words) == 0

    def test_min_length_1(self):
        text = chr(0x0561)
        words = extract_words(text, min_length=1)
        assert len(words) == 1

    def test_non_armenian_excluded(self):
        text = "Hello World"
        words = extract_words(text)
        assert len(words) == 0

    def test_mixed_text(self):
        arm_word = chr(0x0561) + chr(0x0562) + chr(0x0563)
        text = f"Hello {arm_word} World"
        words = extract_words(text)
        assert len(words) == 1

    def test_multiple_words(self):
        w1 = chr(0x0561) + chr(0x0562) + chr(0x0563)
        w2 = chr(0x0564) + chr(0x0565) + chr(0x0566)
        text = f"{w1} {w2}"
        words = extract_words(text)
        assert len(words) == 2


class TestWordFrequencies:
    def test_returns_counter(self):
        w = chr(0x0561) + chr(0x0562) + chr(0x0563)
        text = f"{w} {w} {w}"
        result = word_frequencies(text)
        assert isinstance(result, Counter)
        assert result[w] == 3

    def test_empty_text(self):
        result = word_frequencies("")
        assert len(result) == 0
