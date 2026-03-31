"""Tests for the OCR post-processor (moved from WesternArmenianLLM)."""

from __future__ import annotations

import unicodedata

import pytest

import numpy as np

from hytools.ocr.layout_strategies import score_ocr_text, vertical_valley_column_bounds
from hytools.ocr.postprocessor import (
    decompose_ligatures,
    normalize_unicode,
    normalize_punctuation,
    postprocess,
    remove_garbage_lines,
)
from hytools.ocr.tesseract_config import ARMENIAN_LIGATURES


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


class TestLayoutStrategies:
    def test_score_ocr_text_empty(self):
        assert score_ocr_text("") == 0.0

    def test_score_ocr_text_prefers_letters(self):
        s1 = score_ocr_text("ա")
        s2 = score_ocr_text("|" * 20)
        assert s1 > s2

    def test_vertical_valley_two_columns(self):
        # Wide image: dark left column, white gap, dark right column
        h, w = 100, 400
        g = np.full((h, w), 255, dtype=np.uint8)
        g[:, 0:120] = 30
        g[:, 200:320] = 30
        bounds = vertical_valley_column_bounds(g, min_col_width_px=30, valley_fraction=0.28)
        assert len(bounds) >= 2


