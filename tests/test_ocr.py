"""Tests for the OCR post-processor (moved from WesternArmenianLLM)."""

from __future__ import annotations

import unicodedata

import pytest

from hytool.ocr.postprocessor import (
    decompose_ligatures,
    normalize_unicode,
    normalize_punctuation,
    postprocess,
    remove_garbage_lines,
)
from hytool.ocr.tesseract_config import ARMENIAN_LIGATURES


class TestDecomposeLigatures:
    def test_no_ligatures(self):
        text = "Հայ ժողովուրդ"
        assert decompose_ligatures(text) == text

    def test_known_ligatures_replaced(self):
        for ligature, components in ARMENIAN_LIGATURES.items():
            result = decompose_ligatures(ligature)
            assert result == components, f"Ligature {ligature!r} not correctly decomposed"

    def test_mixed_text(self):
        text = "abc\uFB13xyz"
        result = decompose_ligatures(text)
        assert "\uFB13" not in result


class TestNormalizeUnicode:
    def test_nfc_normalization(self):
        nfd = unicodedata.normalize("NFD", "é")
        assert normalize_unicode(nfd) == "é"

    def test_armenian_unchanged(self):
        text = "Հայաստան"
        assert normalize_unicode(text) == text


class TestRemoveGarbageLines:
    def test_keeps_armenian_lines(self):
        text = "Հայ ժողովուրդ կ՚ապրի"
        result = remove_garbage_lines(text, min_armenian_ratio=0.3)
        assert "Հայ ժողովուրդ" in result

    def test_removes_low_armenian_lines(self):
        text = "@@@@@@@@@@@@@@@@@@ա"
        result = remove_garbage_lines(text, min_armenian_ratio=0.3)
        assert result.strip() == ""

    def test_preserves_empty_lines(self):
        text = "Հայ\n\nժողովուրդ"
        result = remove_garbage_lines(text, min_armenian_ratio=0.3)
        assert "\n\n" in result


class TestPostprocess:
    def test_strips_result(self):
        text = "  Հայ ժողովուրդ  "
        assert not postprocess(text).startswith(" ")

    def test_full_pipeline_armenian(self):
        text = "Հայ ժողովուրդ կ՚ապրի Հայաստանի մէջ"
        result = postprocess(text)
        assert len(result) > 0

    def test_empty_input(self):
        assert postprocess("") == ""

