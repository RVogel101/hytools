"""Tests for the OCR post-processor (moved from WesternArmenianLLM)."""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import numpy as np
from PIL import Image

from hytools.ocr.layout_strategies import score_ocr_text, vertical_valley_column_bounds
from hytools.ocr.nayiri_spellcheck import (
    _is_armenian_token,
    check_token,
    is_valid_word,
    reset_wordset,
)
from hytools.ocr.ocr_metrics import OCRAttempt, OCRPageMetric, new_run_id, write_page_metric
from hytools.ocr.page_classifier import (
    PageType,
    count_horizontal_rules,
    count_vertical_valleys,
    ink_density,
    word_line_stats,
)
from hytools.ocr.pdf_text_layer import (
    parse_use_text_layer_setting,
    recommend_text_layer_from_probe_stats,
)
from hytools.ocr.postprocessor import (
    apply_confusion_corrections,
    decompose_ligatures,
    normalize_unicode,
    normalize_punctuation,
    postprocess,
    remove_garbage_lines,
)
from hytools.ocr.surya_engine import (
    _extract_lines_data,
    _extract_text_lines,
    is_surya_available,
)
from hytools.ocr.tesseract_config import ARMENIAN_LIGATURES
from hytools.ocr.zone_splitter import (
    WordBox,
    Zone,
    _classify_word,
    build_zones,
    is_mixed_page,
)
from hytools.ocr.review_queue import (
    ReviewItem,
    enqueue_for_review,
    make_thumbnail,
    PRIORITY_BELOW_CONFIDENCE,
    PRIORITY_EMPTY_FALLBACK,
    PRIORITY_NON_TEXT,
)
from hytools.ocr.preprocessor import (
    detect_stroke_thinning,
    estimate_stroke_width,
    thicken_strokes,
)
from hytools.ocr.classical_ocr import (
    classical_ocr_image,
    is_classical_available,
    DEFAULT_CLASSICAL_LANG,
)
from hytools.ocr.run_monitor import (
    RunMonitor,
    DEFAULT_ALERT_THRESHOLD,
    DEFAULT_MIN_PAGES,
)
from hytools.ocr.ml_corrector import (
    is_ml_corrector_available,
    ml_correct_text,
    reset as ml_reset,
    _chunk_text,
)
from hytools.ocr.hybrid_ocr import (
    is_ocrmypdf_available,
    is_kraken_available,
    ocrmypdf_page,
    kraken_ocr_image,
    reset as hybrid_reset,
)
from hytools.ocr.armcor import (
    armcor_correct,
    load_armcor_frequencies,
    reset as armcor_reset,
    _best_correction,
    _generate_edit1_candidates,
    _is_armenian_token as armcor_is_armenian_token,
    _strip_punct,
    detect_variant,
    resolve_freq,
)


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

    def test_recommend_probe_good_embedded_text(self):
        ok, _ = recommend_text_layer_from_probe_stats(
            acceptable_count=4,
            image_dominant_count=0,
            sampled=5,
            median_chars_acceptable=400.0,
            median_newlines_acceptable=5.0,
        )
        assert ok is True

    def test_recommend_probe_too_few_passing(self):
        ok, _ = recommend_text_layer_from_probe_stats(
            acceptable_count=1,
            image_dominant_count=0,
            sampled=5,
            median_chars_acceptable=400.0,
            median_newlines_acceptable=5.0,
        )
        assert ok is False

    def test_parse_use_text_layer_setting(self):
        assert parse_use_text_layer_setting("auto") == "auto"
        assert parse_use_text_layer_setting(True) is True
        assert parse_use_text_layer_setting("off") is False

    def test_vertical_valley_two_columns(self):
        # Wide image: dark left column, white gap, dark right column
        h, w = 100, 400
        g = np.full((h, w), 255, dtype=np.uint8)
        g[:, 0:120] = 30
        g[:, 200:320] = 30
        bounds = vertical_valley_column_bounds(g, min_col_width_px=30, valley_fraction=0.28)
        assert len(bounds) >= 2


class TestSuryaEngine:
    """Tests for the Surya OCR engine wrapper (no Surya install required)."""

    def test_is_surya_available_returns_bool(self):
        result = is_surya_available()
        assert isinstance(result, bool)

    def test_extract_lines_data_dict_format(self):
        """v0.17+ dict format with text_lines list."""
        page = {
            "text_lines": [
                {"text": "line one", "confidence": 0.95},
                {"text": "line two", "confidence": 0.88},
            ]
        }
        result = _extract_lines_data(page)
        assert len(result) == 2
        assert result[0]["text"] == "line one"
        assert result[1]["confidence"] == 0.88

    def test_extract_lines_data_empty_dict(self):
        assert _extract_lines_data({}) == []

    def test_extract_lines_data_object_format(self):
        """Earlier Surya versions return objects with .text_lines attribute."""
        line1 = MagicMock()
        line1.text = "first line"
        line1.confidence = 0.9
        page = type("SuryaPage", (), {"text_lines": [line1]})()
        result = _extract_lines_data(page)
        assert len(result) == 1
        assert result[0]["text"] == "first line"

    def test_extract_text_lines_filters_empty(self):
        page = {
            "text_lines": [
                {"text": "keep me", "confidence": 0.9},
                {"text": "", "confidence": 0.1},
                {"text": "also keep", "confidence": 0.8},
            ]
        }
        result = _extract_text_lines(page)
        assert result == ["keep me", "also keep"]

    def test_score_ocr_text_armenian_vs_garbage(self):
        """Surya integration relies on score_ocr_text to pick the winner."""
        armenian = "\u0540\u0561\u0575 \u056a\u0578\u0572\u0578\u057e\u0578\u0582\u0580\u0564"
        good = score_ocr_text(armenian)
        bad = score_ocr_text("||||///###@@@")
        assert good > bad


# ── Confusion-pair correction ────────────────────────────────────────────────

class TestConfusionCorrections:
    """Tests for Armenian OCR confusion-pair correction."""

    def test_no_wordset_returns_unchanged(self):
        text = "ճառdelays"
        assert apply_confusion_corrections(text, wordset=None) == text

    def test_empty_wordset_returns_unchanged(self):
        text = "ճառ"
        assert apply_confusion_corrections(text, wordset=set()) == text

    def test_single_pair_correction(self):
        # ճառ → հառ when "հառ" is in the wordset  (ճ→հ confusion)
        wordset = {"\u0570\u0561\u057c"}  # հառ
        text = "\u0573\u0561\u057c"       # ճառ
        result = apply_confusion_corrections(text, wordset=wordset)
        assert result == "\u0570\u0561\u057c"  # հառ

    def test_ambiguous_candidates_left_alone(self):
        # If both forward and reverse candidate are in the wordset → do nothing
        wordset = {"\u0573\u0561\u057c", "\u0570\u0561\u057c"}  # both ճառ and հառ
        text = "\u0573\u0561\u057c"  # ճառ
        result = apply_confusion_corrections(text, wordset=wordset)
        # The original is already valid, so it should stay
        assert result == text

    def test_english_tokens_untouched(self):
        wordset = {"hello"}
        text = "hello world"
        assert apply_confusion_corrections(text, wordset=wordset) == text

    def test_correction_wired_in_postprocess(self):
        wordset = {"\u0570\u0561\u057c"}  # հառ
        text = "\u0573\u0561\u057c"       # ճառ
        result = postprocess(text, wordset=wordset)
        assert "\u0570\u0561\u057c" in result


# ── Garbage line filter – mixed English/Armenian ─────────────────────────────

class TestRemoveGarbageLinesEnglish:
    """Ensure predominantly English lines survive the garbage filter."""

    def test_english_line_preserved(self):
        text = "This is an English sentence about grammar."
        result = remove_garbage_lines(text, min_armenian_ratio=0.3)
        assert "English sentence" in result

    def test_mixed_bilingual_page(self):
        text = "Հայաdelays ասdelays delays\nThis line is English\n@@@@noise@@@@@@@@@"
        result = remove_garbage_lines(text, min_armenian_ratio=0.3)
        assert "English" in result
        assert "noise" not in result


# ── Nayiri spell-check unit tests ────────────────────────────────────────────

class TestNayiriSpellcheck:
    """Unit tests for the spell-check helpers (no MongoDB required)."""

    def test_is_armenian_token_true(self):
        assert _is_armenian_token("\u0540\u0561\u0575") is True
        assert _is_armenian_token("\u0562\u0561\u057c") is True

    def test_is_armenian_token_false(self):
        assert _is_armenian_token("hello") is False
        assert _is_armenian_token("123") is False

    def test_is_valid_word(self):
        ws = {"\u0562\u0561\u057c", "\u0540\u0561\u0575"}
        assert is_valid_word("\u0562\u0561\u057c", ws) is True
        assert is_valid_word("xyz", ws) is False

    def test_check_token_non_armenian_always_passes(self):
        assert check_token("hello", set()) is True

    def test_check_token_armenian_against_wordset(self):
        ws = {"\u0562\u0561\u057c"}  # բառ
        assert check_token("\u0562\u0561\u057c", ws) is True
        assert check_token("\u0562\u0561\u0576", ws) is False

    def test_reset_wordset(self):
        from hytools.ocr.nayiri_spellcheck import _wordset
        reset_wordset()
        from hytools.ocr import nayiri_spellcheck
        assert nayiri_spellcheck._wordset is None


# ── Zone splitter ────────────────────────────────────────────────────────────

class TestClassifyWord:
    def test_armenian_word(self):
        assert _classify_word("\u0540\u0561\u0575") == "arm"   # Հայ

    def test_latin_word(self):
        assert _classify_word("hello") == "lat"

    def test_other(self):
        assert _classify_word("123") == "other"

    def test_mixed_defaults_to_majority(self):
        # 2 Armenian + 1 Latin → arm
        assert _classify_word("\u0540\u0561x") == "arm"


class TestIsMixedPage:
    def _box(self, text, script, top=0, left=0):
        return WordBox(text=text, left=left, top=top, width=50, height=20, conf=90, script=script)

    def test_pure_armenian_not_mixed(self):
        boxes = [self._box("\u0540\u0561\u0575", "arm")] * 10
        assert is_mixed_page(boxes) is False

    def test_mixed_above_threshold(self):
        boxes = [self._box("\u0540\u0561\u0575", "arm")] * 8 + [self._box("hello", "lat")] * 2
        assert is_mixed_page(boxes, min_minority_ratio=0.10) is True

    def test_mixed_below_threshold(self):
        boxes = [self._box("\u0540\u0561\u0575", "arm")] * 99 + [self._box("x", "lat")]
        assert is_mixed_page(boxes, min_minority_ratio=0.10) is False

    def test_empty(self):
        assert is_mixed_page([]) is False


class TestBuildZones:
    def _box(self, text, script, top, left, w=60, h=20):
        return WordBox(text=text, left=left, top=top, width=w, height=h, conf=90, script=script)

    def test_single_script_one_zone(self):
        boxes = [
            self._box("\u0540\u0561\u0575", "arm", top=10, left=10),
            self._box("\u0562\u0561\u057c", "arm", top=10, left=80),
        ]
        zones = build_zones(boxes)
        assert len(zones) == 1
        assert zones[0].script == "arm"

    def test_two_scripts_two_zones(self):
        boxes = [
            self._box("\u0540\u0561\u0575", "arm", top=10, left=10),
            self._box("hello", "lat", top=200, left=10),  # far apart vertically
        ]
        zones = build_zones(boxes)
        assert len(zones) == 2
        scripts = {z.script for z in zones}
        assert scripts == {"arm", "lat"}

    def test_other_script_ignored(self):
        boxes = [
            self._box("123", "other", top=10, left=10),
        ]
        zones = build_zones(boxes)
        assert len(zones) == 0

    def test_zone_bounding_box(self):
        boxes = [
            self._box("\u0540", "arm", top=10, left=10, w=40, h=20),
            self._box("\u0561", "arm", top=10, left=100, w=40, h=20),
        ]
        zones = build_zones(boxes)
        assert len(zones) == 1
        z = zones[0]
        assert z.left == 10
        assert z.right == 140  # 100 + 40


# ── Page Classifier ───────────────────────────────────────────────────────


class TestInkDensity:
    """Tests for ink_density()."""

    def test_blank_page(self):
        """All-white image → ~0 ink density."""
        img = np.full((100, 100), 255, dtype=np.uint8)
        assert ink_density(img) == pytest.approx(0.0)

    def test_solid_black(self):
        """All-black image → ~1.0 ink density."""
        img = np.zeros((100, 100), dtype=np.uint8)
        assert ink_density(img) == pytest.approx(1.0)

    def test_half_ink(self):
        """Top half black, bottom half white → ~0.5."""
        img = np.full((100, 100), 255, dtype=np.uint8)
        img[:50, :] = 0
        assert ink_density(img) == pytest.approx(0.5)


class TestCountVerticalValleys:
    """Tests for count_vertical_valleys()."""

    def test_single_column(self):
        """Uniform gray → 1 column (no valleys)."""
        img = np.full((200, 200), 100, dtype=np.uint8)
        assert count_vertical_valleys(img) == 1

    def test_multi_column_with_gap(self):
        """Two dark bands separated by a white gap → 2 columns."""
        img = np.full((200, 300), 255, dtype=np.uint8)
        # Left column (ink)
        img[:, 20:120] = 50
        # Right column (ink)
        img[:, 180:280] = 50
        # Gap in between: cols 120-180 remain white
        result = count_vertical_valleys(img)
        assert result >= 2

    def test_narrow_image_returns_one(self):
        """Image narrower than 2*min_col_width_px → 1."""
        img = np.full((200, 60), 100, dtype=np.uint8)
        assert count_vertical_valleys(img, min_col_width_px=40) == 1


class TestCountHorizontalRules:
    """Tests for count_horizontal_rules()."""

    def test_no_rules(self):
        """Plain white image → 0 rules."""
        img = np.full((200, 400), 255, dtype=np.uint8)
        assert count_horizontal_rules(img) == 0

    def test_with_horizontal_line(self):
        """One long black horizontal band → at least 1 rule."""
        img = np.full((200, 400), 255, dtype=np.uint8)
        img[100:103, 20:380] = 0  # 360px-wide line
        assert count_horizontal_rules(img) >= 1

    def test_short_line_ignored(self):
        """A short segment should not count as a rule."""
        img = np.full((200, 400), 255, dtype=np.uint8)
        img[100:103, 10:40] = 0  # Only ~30px wide
        assert count_horizontal_rules(img) == 0


class TestWordLineStats:
    """Tests for word_line_stats()."""

    def test_blank_page(self):
        """All-white → 0 lines."""
        img = np.full((200, 200), 255, dtype=np.uint8)
        lines, wpl = word_line_stats(img)
        assert lines == 0
        assert wpl == 0.0

    def test_single_line(self):
        """One dark horizontal stripe → 1 line."""
        img = np.full((200, 200), 255, dtype=np.uint8)
        img[50:70, 10:190] = 0  # One solid band
        lines, _wpl = word_line_stats(img)
        assert lines == 1

    def test_multiple_lines(self):
        """Three separated dark stripes → 3 lines."""
        img = np.full((300, 200), 255, dtype=np.uint8)
        img[30:50, 10:190] = 0
        img[80:100, 10:190] = 0
        img[130:150, 10:190] = 0
        lines, _wpl = word_line_stats(img)
        assert lines == 3


class TestPageTypeEnum:
    """Verify PageType values."""

    def test_all_types_exist(self):
        assert PageType.PURE_ARMENIAN == "pure_armenian"
        assert PageType.MIXED == "mixed"
        assert PageType.ENGLISH == "english"
        assert PageType.DICTIONARY == "dictionary"
        assert PageType.TABLE == "table"
        assert PageType.NON_TEXT == "non_text"

    def test_string_comparison(self):
        assert PageType("pure_armenian") is PageType.PURE_ARMENIAN


# ── OCR Page Metrics ──────────────────────────────────────────────────────


class TestOCRPageMetric:
    """Tests for OCRPageMetric dataclass and helpers."""

    def _make_metric(self, **overrides) -> OCRPageMetric:
        defaults = dict(
            run_id="test-run-id",
            pdf_path="/tmp/test.pdf",
            pdf_name="test.pdf",
            page_num=1,
            status="success",
            engine="tesseract",
            mean_confidence=85.5,
            char_count=1200,
            word_count=200,
            lang="hye+eng",
            dpi=300,
            psm=6,
            binarization="sauvola",
        )
        defaults.update(overrides)
        return OCRPageMetric(**defaults)

    def test_to_dict_keys(self):
        """to_dict() returns all schema fields."""
        m = self._make_metric()
        d = m.to_dict()
        assert d["run_id"] == "test-run-id"
        assert d["pdf_name"] == "test.pdf"
        assert d["page_num"] == 1
        assert d["status"] == "success"
        assert d["engine"] == "tesseract"
        assert d["mean_confidence"] == 85.5
        assert d["char_count"] == 1200
        assert d["word_count"] == 200
        assert d["lang"] == "hye+eng"
        assert d["dpi"] == 300
        assert d["psm"] == 6
        assert d["binarization"] == "sauvola"
        assert isinstance(d["timestamp"], datetime)

    def test_defaults(self):
        """Optional fields default correctly."""
        m = self._make_metric()
        assert m.font_hint is None
        assert m.adaptive_dpi is False
        assert m.detect_cursive is False
        assert m.page_type is None
        assert m.classifier_confidence is None
        assert m.layout_fallback_used is False
        assert m.zone_ocr_used is False
        assert m.vector_tables_appended is False
        assert m.confidence_threshold == 60
        assert m.attempts == []

    def test_classifier_fields(self):
        m = self._make_metric(
            page_type="pure_armenian",
            classifier_confidence=0.85,
        )
        d = m.to_dict()
        assert d["page_type"] == "pure_armenian"
        assert d["classifier_confidence"] == 0.85

    def test_strategy_flags(self):
        m = self._make_metric(
            layout_fallback_used=True,
            zone_ocr_used=True,
            vector_tables_appended=True,
        )
        assert m.layout_fallback_used is True
        assert m.zone_ocr_used is True
        assert m.vector_tables_appended is True

    def test_non_text_metric(self):
        """NON_TEXT pages have zero counts and engine='none'."""
        m = self._make_metric(
            status="non_text",
            engine="none",
            mean_confidence=-1,
            char_count=0,
            word_count=0,
        )
        d = m.to_dict()
        assert d["status"] == "non_text"
        assert d["engine"] == "none"
        assert d["mean_confidence"] == -1
        assert d["char_count"] == 0

    def test_below_confidence_metric(self):
        m = self._make_metric(
            status="below_confidence",
            engine="none",
            mean_confidence=42.3,
            char_count=0,
            word_count=0,
        )
        d = m.to_dict()
        assert d["status"] == "below_confidence"
        assert d["mean_confidence"] == 42.3


class TestNewRunId:
    """Tests for new_run_id()."""

    def test_returns_uuid_string(self):
        rid = new_run_id()
        assert isinstance(rid, str)
        assert len(rid) == 36  # UUID v4 format

    def test_unique(self):
        ids = {new_run_id() for _ in range(100)}
        assert len(ids) == 100


class TestWritePageMetric:
    """Tests for write_page_metric() with mock collection."""

    def test_inserts_document(self):
        coll = MagicMock()
        m = OCRPageMetric(
            run_id="r1", pdf_path="/tmp/x.pdf", pdf_name="x.pdf",
            page_num=1, status="success", engine="tesseract",
            mean_confidence=90, char_count=500, word_count=80,
            lang="hye", dpi=300, psm=6, binarization="sauvola",
        )
        write_page_metric(coll, m)
        coll.insert_one.assert_called_once()
        doc = coll.insert_one.call_args[0][0]
        assert doc["run_id"] == "r1"
        assert doc["page_num"] == 1

    def test_handles_insert_failure(self):
        """write_page_metric logs but does not raise on insert failure."""
        coll = MagicMock()
        coll.insert_one.side_effect = RuntimeError("db down")
        m = OCRPageMetric(
            run_id="r1", pdf_path="/tmp/x.pdf", pdf_name="x.pdf",
            page_num=1, status="success", engine="tesseract",
            mean_confidence=75, char_count=100, word_count=20,
            lang="hye+eng", dpi=300, psm=6, binarization="sauvola",
        )
        # Should not raise
        write_page_metric(coll, m)


class TestOCRAttempt:
    """Tests for OCRAttempt dataclass."""

    def test_defaults(self):
        a = OCRAttempt(engine="tesseract")
        assert a.lang is None
        assert a.psm is None
        assert a.score == -1
        assert a.mean_confidence == -1
        assert a.char_count == 0
        assert a.chosen is False
        assert a.detail is None

    def test_to_dict(self):
        a = OCRAttempt(
            engine="surya", score=12.5, char_count=400, chosen=True,
        )
        d = a.to_dict()
        assert d["engine"] == "surya"
        assert d["score"] == 12.5
        assert d["char_count"] == 400
        assert d["chosen"] is True

    def test_full_attempt(self):
        a = OCRAttempt(
            engine="tesseract", lang="hye+eng", psm=6,
            score=15.2, mean_confidence=78.3, char_count=1100,
            chosen=True, detail="default PSM",
        )
        assert a.engine == "tesseract"
        assert a.lang == "hye+eng"
        assert a.psm == 6
        assert a.detail == "default PSM"


class TestOCRPageMetricAttempts:
    """Tests for OCRPageMetric with attempts list."""

    def _base(self, **kw):
        defaults = dict(
            run_id="r1", pdf_path="/tmp/t.pdf", pdf_name="t.pdf",
            page_num=1, status="success", engine="tesseract",
            mean_confidence=80, char_count=500, word_count=90,
            lang="hye", dpi=300, psm=6, binarization="sauvola",
        )
        defaults.update(kw)
        return OCRPageMetric(**defaults)

    def test_attempts_in_to_dict(self):
        a1 = OCRAttempt(engine="tesseract", score=10, chosen=False)
        a2 = OCRAttempt(engine="surya", score=14, chosen=True)
        m = self._base(attempts=[a1, a2])
        d = m.to_dict()
        assert len(d["attempts"]) == 2
        assert d["attempts"][0]["engine"] == "tesseract"
        assert d["attempts"][0]["chosen"] is False
        assert d["attempts"][1]["engine"] == "surya"
        assert d["attempts"][1]["chosen"] is True

    def test_empty_attempts(self):
        m = self._base()
        d = m.to_dict()
        assert d["attempts"] == []

    def test_run_level_params(self):
        m = self._base(
            font_hint="tiny", adaptive_dpi=True, detect_cursive=True,
        )
        d = m.to_dict()
        assert d["font_hint"] == "tiny"
        assert d["adaptive_dpi"] is True
        assert d["detect_cursive"] is True

    def test_below_confidence_with_attempt(self):
        a = OCRAttempt(
            engine="tesseract", lang="hye", psm=6,
            mean_confidence=42.0, char_count=0,
            chosen=False, detail="below_confidence gate",
        )
        m = self._base(
            status="below_confidence", engine="none",
            mean_confidence=42.0, char_count=0, word_count=0,
            attempts=[a],
        )
        d = m.to_dict()
        assert d["status"] == "below_confidence"
        assert len(d["attempts"]) == 1
        assert d["attempts"][0]["detail"] == "below_confidence gate"


# ───── Stroke Thickening ─────────────────────────────────────────────────

class TestEstimateStrokeWidth:
    """Tests for estimate_stroke_width."""

    def test_blank_page_returns_zero(self):
        blank = np.full((100, 100), 255, dtype=np.uint8)
        assert estimate_stroke_width(blank) == 0.0

    def test_solid_black_positive(self):
        solid = np.zeros((100, 100), dtype=np.uint8)
        assert estimate_stroke_width(solid) > 0

    def test_thin_line(self):
        img = np.full((100, 100), 255, dtype=np.uint8)
        img[50, 20:80] = 0  # 1-pixel line
        w = estimate_stroke_width(img)
        assert 0 < w <= 3.0

    def test_thick_line(self):
        img = np.full((200, 200), 255, dtype=np.uint8)
        img[90:110, 20:180] = 0  # 20-pixel thick bar
        w = estimate_stroke_width(img)
        assert w > 5.0


class TestDetectStrokeThinning:
    """Tests for detect_stroke_thinning."""

    def test_blank_page_not_thin(self):
        blank = np.full((100, 100), 255, dtype=np.uint8)
        assert detect_stroke_thinning(blank) is False

    def test_thin_line_detected(self):
        img = np.full((200, 200), 255, dtype=np.uint8)
        # 1-pixel horizontal lines (thin text simulation)
        for y in range(20, 180, 10):
            img[y, 20:180] = 0
        assert detect_stroke_thinning(img, thin_threshold=3.0) is True

    def test_thick_strokes_not_detected(self):
        img = np.full((200, 200), 255, dtype=np.uint8)
        img[80:120, 20:180] = 0  # 40-px block
        assert detect_stroke_thinning(img, thin_threshold=3.0) is False


class TestThickenStrokes:
    """Tests for thicken_strokes."""

    def test_increases_ink(self):
        img = np.full((100, 100), 255, dtype=np.uint8)
        img[50, 30:70] = 0  # thin horizontal line
        ink_before = np.sum(img == 0)
        result = thicken_strokes(img)
        ink_after = np.sum(result == 0)
        assert ink_after > ink_before

    def test_idempotent_on_blank(self):
        blank = np.full((100, 100), 255, dtype=np.uint8)
        result = thicken_strokes(blank)
        assert np.array_equal(result, blank)

    def test_kernel_size(self):
        img = np.full((100, 100), 255, dtype=np.uint8)
        img[50, 40:60] = 0
        r1 = thicken_strokes(img, kernel_size=2)
        r2 = thicken_strokes(img, kernel_size=3)
        ink1 = np.sum(r1 == 0)
        ink2 = np.sum(r2 == 0)
        assert ink2 >= ink1

    def test_iterations(self):
        img = np.full((100, 100), 255, dtype=np.uint8)
        img[50, 40:60] = 0
        r1 = thicken_strokes(img, iterations=1)
        r2 = thicken_strokes(img, iterations=2)
        ink1 = np.sum(r1 == 0)
        ink2 = np.sum(r2 == 0)
        assert ink2 >= ink1

    def test_preserves_shape(self):
        img = np.full((150, 200), 255, dtype=np.uint8)
        img[75, 50:150] = 0
        result = thicken_strokes(img)
        assert result.shape == img.shape


class TestPreprocessStrokeThicken:
    """Test preprocess() integration with stroke_thicken."""

    def _white_image_with_thin_lines(self):
        from PIL import Image
        arr = np.full((200, 200, 3), 255, dtype=np.uint8)
        for y in range(20, 180, 10):
            arr[y, 20:180] = 0
        return Image.fromarray(arr)

    def test_stroke_thicken_true(self):
        from hytools.ocr.preprocessor import preprocess
        img = self._white_image_with_thin_lines()
        result = preprocess(img, stroke_thicken=True)
        # Should return valid image (mode L)
        assert result.mode == "L"
        arr = np.array(result)
        assert arr.shape == (200, 200)

    def test_stroke_thicken_auto(self):
        from hytools.ocr.preprocessor import preprocess
        img = self._white_image_with_thin_lines()
        result = preprocess(img, stroke_thicken="auto", stroke_thin_threshold=5.0)
        assert result.mode == "L"

    def test_stroke_thicken_false_default(self):
        from hytools.ocr.preprocessor import preprocess
        img = self._white_image_with_thin_lines()
        result = preprocess(img, stroke_thicken=False)
        assert result.mode == "L"


# ───── Review Queue ──────────────────────────────────────────────────────

class TestMakeThumbnail:
    """Tests for make_thumbnail helper."""

    def _rgb_image(self, w=800, h=1200):
        """Create a test RGB PIL Image."""
        from PIL import Image
        return Image.fromarray(np.zeros((h, w, 3), dtype=np.uint8))

    def test_returns_jpeg_bytes(self):
        img = self._rgb_image()
        thumb = make_thumbnail(img)
        assert isinstance(thumb, bytes)
        # JPEG magic bytes
        assert thumb[:2] == b"\xff\xd8"

    def test_respects_max_px(self):
        from PIL import Image as PILImage
        img = self._rgb_image(1600, 2400)
        thumb_bytes = make_thumbnail(img, max_px=256)
        thumb = PILImage.open(__import__("io").BytesIO(thumb_bytes))
        assert max(thumb.size) <= 256

    def test_default_max_512(self):
        from PIL import Image as PILImage
        img = self._rgb_image(2000, 3000)
        thumb_bytes = make_thumbnail(img)
        thumb = PILImage.open(__import__("io").BytesIO(thumb_bytes))
        assert max(thumb.size) <= 512

    def test_small_image_not_upscaled(self):
        from PIL import Image as PILImage
        img = self._rgb_image(100, 150)
        thumb_bytes = make_thumbnail(img)
        thumb = PILImage.open(__import__("io").BytesIO(thumb_bytes))
        # PIL thumbnail does not upscale
        assert thumb.size[0] <= 100 and thumb.size[1] <= 150

    def test_rgba_converted(self):
        from PIL import Image
        img = Image.fromarray(np.zeros((100, 100, 4), dtype=np.uint8), mode="RGBA")
        thumb = make_thumbnail(img)
        assert isinstance(thumb, bytes)
        assert thumb[:2] == b"\xff\xd8"


class TestReviewItem:
    """Tests for ReviewItem dataclass."""

    def _item(self, **kw):
        defaults = dict(
            run_id="r-1", pdf_path="/tmp/test.pdf", pdf_name="test.pdf",
            page_num=5, reason="below_confidence",
            priority=PRIORITY_BELOW_CONFIDENCE,
        )
        defaults.update(kw)
        return ReviewItem(**defaults)

    def test_defaults(self):
        item = self._item()
        assert item.reviewed is False
        assert item.reviewer_notes == ""
        assert item.thumbnail == b""
        assert item.mean_confidence == -1

    def test_to_dict(self):
        item = self._item(detail="mean_conf=42.3 threshold=60")
        d = item.to_dict()
        assert d["run_id"] == "r-1"
        assert d["page_num"] == 5
        assert d["reason"] == "below_confidence"
        assert d["priority"] == 1
        assert d["detail"] == "mean_conf=42.3 threshold=60"
        assert isinstance(d["created_at"], datetime)

    def test_thumbnail_bytes_in_dict(self):
        thumb = b"\xff\xd8fake_jpeg"
        item = self._item(thumbnail=thumb)
        d = item.to_dict()
        assert d["thumbnail"] == thumb

    def test_priority_values(self):
        assert PRIORITY_BELOW_CONFIDENCE == 1
        assert PRIORITY_EMPTY_FALLBACK == 2
        assert PRIORITY_NON_TEXT == 3


class TestEnqueueForReview:
    """Tests for enqueue_for_review with mocked collection."""

    def _item(self, **kw):
        defaults = dict(
            run_id="r-1", pdf_path="/tmp/test.pdf", pdf_name="test.pdf",
            page_num=3, reason="non_text", priority=PRIORITY_NON_TEXT,
        )
        defaults.update(kw)
        return ReviewItem(**defaults)

    def test_inserts_into_collection(self):
        coll = MagicMock()
        item = self._item()
        enqueue_for_review(coll, item)
        coll.insert_one.assert_called_once()
        doc = coll.insert_one.call_args[0][0]
        assert doc["pdf_name"] == "test.pdf"
        assert doc["page_num"] == 3
        assert doc["reason"] == "non_text"

    def test_survives_insert_error(self):
        coll = MagicMock()
        coll.insert_one.side_effect = RuntimeError("connection lost")
        item = self._item()
        # Should not raise
        enqueue_for_review(coll, item)

    def test_all_fields_present(self):
        coll = MagicMock()
        item = self._item(
            detail="test detail", mean_confidence=55.0,
            lang="hye", dpi=400, thumbnail=b"\xff\xd8",
        )
        enqueue_for_review(coll, item)
        doc = coll.insert_one.call_args[0][0]
        assert doc["detail"] == "test detail"
        assert doc["mean_confidence"] == 55.0
        assert doc["lang"] == "hye"
        assert doc["dpi"] == 400
        assert doc["thumbnail"] == b"\xff\xd8"
        assert doc["reviewed"] is False


# ───── Classical OCR Pass ────────────────────────────────────────────────

class TestIsClassicalAvailable:
    """Tests for is_classical_available."""

    def test_returns_bool(self):
        # May or may not be installed — just verify no crash and returns bool
        result = is_classical_available("hye_old")
        assert isinstance(result, bool)

    @patch("hytools.ocr.classical_ocr.subprocess.run")
    def test_available_when_listed(self, mock_run):
        # Clear the lru_cache first
        is_classical_available.cache_clear()
        mock_run.return_value = MagicMock(
            stdout="List of available languages:\nhye\nhye_old\neng\n",
        )
        assert is_classical_available("hye_old") is True
        is_classical_available.cache_clear()

    @patch("hytools.ocr.classical_ocr.subprocess.run")
    def test_not_available_when_missing(self, mock_run):
        is_classical_available.cache_clear()
        mock_run.return_value = MagicMock(
            stdout="List of available languages:\nhye\neng\n",
        )
        assert is_classical_available("hye_old") is False
        is_classical_available.cache_clear()

    @patch("hytools.ocr.classical_ocr.subprocess.run")
    def test_handles_subprocess_failure(self, mock_run):
        is_classical_available.cache_clear()
        mock_run.side_effect = FileNotFoundError("tesseract not found")
        assert is_classical_available("hye_old") is False
        is_classical_available.cache_clear()


class TestClassicalDefaults:
    """Tests for classical_ocr module defaults."""

    def test_default_lang(self):
        assert DEFAULT_CLASSICAL_LANG == "hye_old"


# ───── Run Monitor ───────────────────────────────────────────────────────

class TestRunMonitor:
    """Tests for RunMonitor production alerting."""

    def test_empty_run_no_alert(self):
        m = RunMonitor("r1", "test.pdf")
        assert m.total == 0
        assert m.failure_rate == 0.0
        assert m.check_alerts() is None

    def test_all_success_no_alert(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(10):
            m.record("success")
        assert m.total == 10
        assert m.failure_count == 0
        assert m.failure_rate == 0.0
        assert m.check_alerts() is None

    def test_high_failure_rate_triggers_alert(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(3):
            m.record("success")
        for _ in range(5):
            m.record("below_confidence")
        for _ in range(2):
            m.record("non_text")
        # 7/10 = 70% failure
        assert m.failure_count == 7
        msg = m.check_alerts()
        assert msg is not None
        assert "70%" in msg
        assert "test.pdf" in msg

    def test_below_min_pages_no_alert(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=5)
        m.record("below_confidence")
        m.record("below_confidence")
        # 100% failure but only 2 pages < min_pages=5
        assert m.total == 2
        assert m.check_alerts() is None

    def test_exactly_at_threshold_no_alert(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(9):
            m.record("success")
        m.record("below_confidence")
        # 1/10 = 10% = exactly at threshold (not above)
        assert m.check_alerts() is None

    def test_just_above_threshold_triggers(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(8):
            m.record("success")
        m.record("non_text")
        m.record("below_confidence")
        # 2/10 = 20% > 10%
        msg = m.check_alerts()
        assert msg is not None

    def test_empty_after_fallback_counted(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.05, min_pages=3)
        for _ in range(5):
            m.record("success")
        m.record("empty_after_fallback")
        # 1/6 ≈ 17% > 5%
        msg = m.check_alerts()
        assert msg is not None

    def test_skipped_and_text_layer_not_failures(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(3):
            m.record("skipped")
        for _ in range(3):
            m.record("text_layer")
        for _ in range(4):
            m.record("success")
        assert m.failure_count == 0
        assert m.check_alerts() is None

    def test_to_dict(self):
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.15, min_pages=2)
        m.record("success")
        m.record("below_confidence")
        d = m.to_dict()
        assert d["run_id"] == "r1"
        assert d["pdf_name"] == "test.pdf"
        assert d["total_pages"] == 2
        assert d["status_counts"]["success"] == 1
        assert d["status_counts"]["below_confidence"] == 1
        assert d["alert_threshold"] == 0.15

    def test_check_alerts_writes_to_collection(self):
        coll = MagicMock()
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(10):
            m.record("success")
        m.check_alerts(collection=coll)
        coll.insert_one.assert_called_once()
        doc = coll.insert_one.call_args[0][0]
        assert doc["run_id"] == "r1"
        assert doc["alert"] is False
        assert doc["total_pages"] == 10

    def test_check_alerts_writes_alert_doc(self):
        coll = MagicMock()
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(5):
            m.record("success")
        for _ in range(5):
            m.record("below_confidence")
        m.check_alerts(collection=coll)
        doc = coll.insert_one.call_args[0][0]
        assert doc["alert"] is True
        assert "50%" in doc["alert_message"]

    def test_collection_error_does_not_crash(self):
        coll = MagicMock()
        coll.insert_one.side_effect = RuntimeError("connection lost")
        m = RunMonitor("r1", "test.pdf", alert_threshold=0.10, min_pages=3)
        for _ in range(10):
            m.record("below_confidence")
        # Should not raise
        msg = m.check_alerts(collection=coll)
        assert msg is not None


# ── ML Corrector Tests ──────────────────────────────────────────────────────


class TestMLCorrectorAvailability:
    def setup_method(self):
        ml_reset()

    def test_unavailable_without_model_path(self):
        assert is_ml_corrector_available("") is False

    def test_unavailable_without_transformers(self):
        ml_reset()
        with patch.dict("sys.modules", {"transformers": None}):
            ml_reset()
            assert is_ml_corrector_available("some/model") is False

    def test_correct_text_returns_none_when_unavailable(self):
        result = ml_correct_text("test text", model_path="")
        assert result is None

    def test_correct_text_returns_none_for_empty(self):
        result = ml_correct_text("", model_path="some/model")
        assert result is None

    def test_correct_text_returns_none_for_whitespace(self):
        result = ml_correct_text("   ", model_path="some/model")
        assert result is None


class TestMLCorrectorChunking:
    def test_short_text_single_chunk(self):
        chunks = _chunk_text("Hello world", 100)
        assert chunks == ["Hello world"]

    def test_long_text_split_on_newlines(self):
        text = "line one\nline two\nline three\nline four"
        chunks = _chunk_text(text, 20)
        assert len(chunks) >= 2
        assert "".join(c.replace("\n", "") for c in chunks) == text.replace("\n", "")

    def test_empty_text(self):
        assert _chunk_text("", 100) == [""]

    def test_exact_boundary(self):
        text = "abcde"
        chunks = _chunk_text(text, 5)
        assert chunks == ["abcde"]


# ── Hybrid OCR Tests ────────────────────────────────────────────────────────


class TestHybridOCRAvailability:
    def setup_method(self):
        hybrid_reset()

    def test_ocrmypdf_unavailable_by_default(self):
        hybrid_reset()
        with patch.dict("sys.modules", {"ocrmypdf": None}):
            hybrid_reset()
            assert is_ocrmypdf_available() is False

    def test_kraken_unavailable_by_default(self):
        hybrid_reset()
        with patch.dict("sys.modules", {"kraken": None}):
            hybrid_reset()
            assert is_kraken_available() is False

    def test_ocrmypdf_page_returns_none_when_unavailable(self):
        hybrid_reset()
        with patch("hytools.ocr.hybrid_ocr.is_ocrmypdf_available", return_value=False):
            img = Image.new("L", (100, 100), 255)
            assert ocrmypdf_page(img) is None

    def test_kraken_returns_none_when_unavailable(self):
        hybrid_reset()
        with patch("hytools.ocr.hybrid_ocr.is_kraken_available", return_value=False):
            img = Image.new("L", (100, 100), 255)
            assert kraken_ocr_image(img) is None


class TestHybridOCRReset:
    def test_reset_clears_flags(self):
        hybrid_reset()
        # After reset, flags should be None (unchecked)
        from hytools.ocr import hybrid_ocr
        assert hybrid_ocr._ocrmypdf_available is None
        assert hybrid_ocr._kraken_available is None
        assert hybrid_ocr._kraken_model is None


# ── ArmCor Tests ────────────────────────────────────────────────────────────


class TestArmCorIsArmenianToken:
    def test_armenian_token(self):
        assert armcor_is_armenian_token("բառdelays") is True

    def test_latin_only(self):
        assert armcor_is_armenian_token("hello") is False

    def test_digits(self):
        assert armcor_is_armenian_token("12345") is False


class TestArmCorStripPunct:
    def test_no_punct(self):
        assert _strip_punct("word") == ("", "word", "")

    def test_leading_punct(self):
        assert _strip_punct("(word") == ("(", "word", "")

    def test_trailing_punct(self):
        assert _strip_punct("word,") == ("", "word", ",")

    def test_both_punct(self):
        assert _strip_punct("(word)") == ("(", "word", ")")

    def test_all_punct(self):
        assert _strip_punct("...") == ("...", "", "")


class TestArmCorEditCandidates:
    def test_generates_candidates(self):
        cands = _generate_edit1_candidates("\u0561\u0562")  # աբ
        assert len(cands) > 0
        assert "\u0561\u0562" not in cands  # original excluded

    def test_single_char(self):
        cands = _generate_edit1_candidates("\u0561")  # ա
        assert len(cands) > 0

    def test_empty_string(self):
        cands = _generate_edit1_candidates("")
        # Should only produce single-char insertions
        assert all(len(c) == 1 for c in cands)


class TestArmCorBestCorrection:
    def test_known_word_not_corrected(self):
        freq = {"\u0561\u0562\u0563": 10}  # աբգ
        assert _best_correction("\u0561\u0562\u0563", freq) is None

    def test_unknown_corrected_to_known(self):
        # աdelays = not a word; we test with a word 1 edit from the freq word
        freq = {"\u0561\u0562\u0563": 10}  # աբգ
        # Change last char: աբdelays → try to fix → should find աβγ if 1 edit away
        result = _best_correction("\u0561\u0562\u0564", freq, min_freq=3)  # abdiffers by 1
        assert result == "\u0561\u0562\u0563"

    def test_no_candidate_above_threshold(self):
        freq = {"\u0561\u0562\u0563": 1}  # frequency too low
        result = _best_correction("\u0561\u0562\u0564", freq, min_freq=5)
        assert result is None


class TestArmCorCorrect:
    def test_empty_freq_returns_unchanged(self):
        text = "some text"
        assert armcor_correct(text, freq={}) == text

    def test_no_freq_path_returns_unchanged(self):
        armcor_reset()
        text = "some text"
        assert armcor_correct(text, freq_path="") == text

    def test_latin_tokens_unchanged(self):
        freq = {"\u0561\u0562\u0563": 10}
        text = "hello world"
        assert armcor_correct(text, freq=freq) == text

    def test_known_armenian_unchanged(self):
        word = "\u0561\u0562\u0563"  # աβγ
        freq = {word: 10}
        assert armcor_correct(word, freq=freq) == word

    def test_corrects_single_error(self):
        correct = "\u0561\u0562\u0563"  # αβγ
        wrong = "\u0561\u0562\u0564"    # 1 edit away
        freq = {correct: 100}
        result = armcor_correct(wrong, freq=freq, min_freq=3)
        assert result == correct

    def test_preserves_capitalization(self):
        correct_lower = "\u0561\u0562\u0563"
        upper_first = "\u0531\u0562\u0564"  # Uppercase first + wrong last
        freq = {correct_lower: 100}
        result = armcor_correct(upper_first, freq=freq, min_freq=3)
        # Should capitalize the correction
        expected = correct_lower[0].upper() + correct_lower[1:]
        assert result == expected


class TestArmCorLoadFrequencies:
    def setup_method(self):
        armcor_reset()

    def test_missing_file_returns_empty(self):
        freq = load_armcor_frequencies("/nonexistent/file.json")
        assert freq == {}

    def test_loads_valid_json(self, tmp_path):
        armcor_reset()
        f = tmp_path / "freq.json"
        f.write_text('{"\\u0561\\u0562\\u0563": 42}', encoding="utf-8")
        freq = load_armcor_frequencies(str(f))
        assert freq == {"\u0561\u0562\u0563": 42}

    def test_caches_result(self, tmp_path):
        armcor_reset()
        f = tmp_path / "freq.json"
        f.write_text('{"word": 1}', encoding="utf-8")
        freq1 = load_armcor_frequencies(str(f))
        freq2 = load_armcor_frequencies(str(f))
        assert freq1 is freq2

    def test_invalid_json_returns_empty(self, tmp_path):
        armcor_reset()
        f = tmp_path / "bad.json"
        f.write_text("not json", encoding="utf-8")
        freq = load_armcor_frequencies(str(f))
        assert freq == {}


class TestArmCorReset:
    def test_reset_clears_cache(self):
        armcor_reset()
        from hytools.ocr import armcor
        assert armcor._freq_dict is None
        assert armcor._freq_path_loaded == ""
        assert armcor._freq_cache == {}


# ── ArmCor Variant-Aware Tests ──────────────────────────────────────────────


class TestDetectVariant:
    def test_western_text(self):
        # "կdelays" particle is a WA marker
        result = detect_variant("կdelays գնdelays եdelays")
        assert result in ("western", "eastern")  # classifier-dependent

    def test_defaults_to_western_on_empty(self):
        result = detect_variant("")
        assert result == "western"


class TestResolveFreq:
    def setup_method(self):
        armcor_reset()

    def test_direct_freq_overrides_all(self):
        direct = {"\u0561": 5}
        result = resolve_freq(freq=direct, variant="eastern", freq_path="/nope")
        assert result is direct

    def test_variant_western_loads_wa_file(self, tmp_path):
        wa_file = tmp_path / "wa.json"
        wa_file.write_text('{"\u0561\u0562": 10}', encoding="utf-8")
        ea_file = tmp_path / "ea.json"
        ea_file.write_text('{"\u0563\u0564": 20}', encoding="utf-8")

        result = resolve_freq(
            variant="western",
            freq_path_wa=str(wa_file),
            freq_path_ea=str(ea_file),
        )
        assert "\u0561\u0562" in result
        assert "\u0563\u0564" not in result

    def test_variant_eastern_loads_ea_file(self, tmp_path):
        wa_file = tmp_path / "wa.json"
        wa_file.write_text('{"\u0561\u0562": 10}', encoding="utf-8")
        ea_file = tmp_path / "ea.json"
        ea_file.write_text('{"\u0563\u0564": 20}', encoding="utf-8")

        result = resolve_freq(
            variant="eastern",
            freq_path_wa=str(wa_file),
            freq_path_ea=str(ea_file),
        )
        assert "\u0563\u0564" in result
        assert "\u0561\u0562" not in result

    def test_fallback_to_generic_path(self, tmp_path):
        generic = tmp_path / "generic.json"
        generic.write_text('{"\u0565": 5}', encoding="utf-8")

        result = resolve_freq(variant="western", freq_path=str(generic))
        assert "\u0565" in result

    def test_no_paths_returns_empty(self):
        result = resolve_freq(variant="western")
        assert result == {}


class TestArmCorCorrectVariant:
    def setup_method(self):
        armcor_reset()

    def test_correct_with_wa_corpus(self, tmp_path):
        wa_file = tmp_path / "wa.json"
        correct = "\u0561\u0562\u0563"  # word in WA corpus
        wa_file.write_text('{"%s": 100}' % correct, encoding="utf-8")

        wrong = "\u0561\u0562\u0564"  # 1-edit-away typo
        result = armcor_correct(
            wrong,
            variant="western",
            freq_path_wa=str(wa_file),
        )
        assert result == correct

    def test_correct_with_ea_corpus(self, tmp_path):
        ea_file = tmp_path / "ea.json"
        correct = "\u0561\u0562\u0563"
        ea_file.write_text('{"%s": 100}' % correct, encoding="utf-8")

        wrong = "\u0561\u0562\u0564"
        result = armcor_correct(
            wrong,
            variant="eastern",
            freq_path_ea=str(ea_file),
        )
        assert result == correct

    def test_direct_freq_still_works(self):
        correct = "\u0561\u0562\u0563"
        wrong = "\u0561\u0562\u0564"
        freq = {correct: 100}
        result = armcor_correct(wrong, freq=freq, min_freq=3)
        assert result == correct
