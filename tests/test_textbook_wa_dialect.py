"""
Tests using Textbook of Modern Western Armenian vocabulary and example sentences.

Data source: tests/data/textbook_modern_wa_vocab_and_sentences.json
- Populated from TEST_VALIDATION_ARMENIAN.md and dialect_classifier examples.
- When the textbook PDF is extracted (OCR or manual), add its vocabulary and
  example sentences to the JSON; these tests then serve as the standard
  for dialect classification and grammar validation.

The dialect classifier is rule-based and returns "inconclusive" when no
documented marker (e.g. կը, մը, իւ for WA; մի, ձու, reformed spellings for EA)
appears. Tests therefore assert "not the wrong dialect" so that sentences
without markers do not fail; sentences that contain markers must still
classify correctly.

Reference: docs/armenian_language_guids/TEXTBOOK_MODERN_WESTERN_ARMENIAN_GRAMMAR.md
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from hytools.ingestion._shared.helpers import classify_text_classification


def _load_textbook_data():
    path = Path(__file__).resolve().parent / "data" / "textbook_modern_wa_vocab_and_sentences.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestTextbookWesternSentences(unittest.TestCase):
    """Western examples must not be classified as Eastern; Eastern must not be classified as Western."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_textbook_data()

    def test_data_file_exists(self):
        self.assertIsNotNone(self.data, "textbook_modern_wa_vocab_and_sentences.json not found")

    def test_western_sentences_not_eastern(self):
        """Western Armenian sentences must not be classified as likely_eastern."""
        if not self.data:
            self.skipTest("No textbook data")
        for text in self.data.get("sentences_western", []):
            with self.subTest(text=text[:50]):
                result = classify_text_classification(text)
                self.assertNotEqual(
                    result.get("label"),
                    "likely_eastern",
                    f"Western example must not be Eastern: {text!r} -> {result.get('label')}",
                )

    def test_western_sentences_with_markers_classify_as_western(self):
        """Sentences that contain known WA markers (e.g. կը, մը, իւ) must classify as likely_western."""
        if not self.data:
            self.skipTest("No textbook data")
        # Subset that contains documented WA markers so classifier can score them
        with_markers = [
            "Ան կը խօսի հայերէն, հոն կ՚ապրի մէջ իւրաքանչիւր մանուկ",
            "մէջ իւրաքանչիւր բան մը",
            "կը խօսի հայերէն",
            "Ես կը սիրեմ հայերէն։",
            "Ես եւ ան կը խօսին միայն հայերէն։",
            "Ինքզինքս կը սիրեմ։",
        ]
        for text in with_markers:
            with self.subTest(text=text[:50]):
                result = classify_text_classification(text)
                self.assertEqual(
                    result.get("label"),
                    "likely_western",
                    f"Expected likely_western (has WA markers): {text!r} -> {result.get('label')} (W={result.get('western_score')} E={result.get('eastern_score')})",
                )

    def test_eastern_sentences_not_western(self):
        """Eastern Armenian sentences must not be classified as likely_western."""
        if not self.data:
            self.skipTest("No textbook data")
        for text in self.data.get("sentences_eastern", []):
            with self.subTest(text=text[:50]):
                result = classify_text_classification(text)
                self.assertNotEqual(
                    result.get("label"),
                    "likely_western",
                    f"Eastern example must not be Western: {text!r} -> {result.get('label')}",
                )

    def test_eastern_sentences_with_markers_classify_as_eastern(self):
        """Sentences that contain known EA markers (e.g. մի, ձու, reformed spelling) must classify as likely_eastern."""
        if not self.data:
            self.skipTest("No textbook data")
        # Subset with documented EA markers
        with_markers = [
            "մի խնձոր ունեմ",  # EA indefinite article "մի" before noun
        ]
        for text in with_markers:
            with self.subTest(text=text[:50]):
                result = classify_text_classification(text)
                self.assertEqual(
                    result.get("label"),
                    "likely_eastern",
                    f"Expected likely_eastern (has EA markers): {text!r} -> {result.get('label')} (W={result.get('western_score')} E={result.get('eastern_score')})",
                )

    def test_vocabulary_has_no_eastern_markers(self):
        """Vocabulary words (WA) should not be classified as Eastern."""
        if not self.data:
            self.skipTest("No textbook data")
        vocab = self.data.get("vocabulary", [])
        for word in vocab:
            with self.subTest(word=word):
                result = classify_text_classification(word)
                self.assertNotEqual(
                    result.get("label"),
                    "likely_eastern",
                    f"WA vocabulary should not be Eastern: {word!r} -> {result.get('label')}",
                )


class TestTextbookDataStructure(unittest.TestCase):
    """Ensure textbook JSON has the expected structure for future textbook content."""

    def test_required_keys(self):
        data = _load_textbook_data()
        if not data:
            self.skipTest("No textbook data")
        for key in ("vocabulary", "sentences_western", "sentences_eastern"):
            self.assertIn(key, data, f"Missing key: {key}")
            self.assertIsInstance(data[key], list, f"{key} should be a list")


class TestWaScoreUnitExtras(unittest.TestCase):
    """Additional WA scoring tests originally added from WesternArmenianLLM."""

    def test_wa_present_onset_gu(self):
        # ԱՆ ԿՈՒ ԳԱՅ ԵՎ ՄԵՑ ՇՏԱՊՈՒՄ ՈՒՆԻ
        text = "\u0531\u0576 \u056f\u0578\u0582 \u0563\u0561\u0575 \u0587 \u0574\u0565\u056e \u0577\u057f\u0561\u057a\u0578\u0582\u0574 \u0578\u0582\u0576\u056b"
        result = classify_text_classification(text)
        self.assertEqual(result.get("label"), "likely_western")

    def test_wa_case_dative_within(self):
        # ՄԵԶԻ ՄԵՑ ՏՈՒՆԸ ՃԱՄԲԱՌԸ ՍԿՍԱՒ
        text = "\u0544\u0565\u0566\u056b \u0574\u0567\u057b \u057f\u0578\u0582\u0576\u0568 \u0573\u0561\u0574\u0562\u0561\u0580\u0568 \u057d\u056f\u057d\u0561\u0582"
        result = classify_text_classification(text)
        self.assertEqual(result.get("label"), "likely_western")

    def test_wa_neg_conjunction_ayl(self):
        # ՆԱ ԱՅԼԵՒՍ ՉԸՍԵՐ ԱՅՍ ՈՃԸ
        text = "\u0546\u0561 \u0561\u0575\u056c\u0565\u0582\u057d \u0579\u0568\u057d\u0565\u0580 \u0561\u0575\u057d \u0578\u0573\u0568"
        result = classify_text_classification(text)
        self.assertEqual(result.get("label"), "likely_western")

    def test_wa_verb_participle_u(self):
        # ԽԱՂԱԼՈՒ ԺԱՄԱՆԱԿԸ ՄԻՇՏ ՈՒՐԱԽ Է
        text = "\u053d\u0561\u0572\u0561\u056c\u0578\u0582 \u056a\u0561\u0574\u0561\u056f\u0568 \u0574\u056b\u0577\u057f \u0578\u0582\u0580\u0561\u0563 \u0565"
        result = classify_text_classification(text)
        self.assertEqual(result.get("label"), "likely_western")

    def test_wa_vocabulary_core_words(self):
        # ՇԱՏ ԼԱՒ ՄԵՑ ՄԱՐԴԸ ՊԱՏՄԵՑ
        text = "\u0547\u0561\u0570 \u056c\u0561\u057e \u0574\u0565\u056e \u0574\u0561\u0572\u0564\u056b\u0578\u057e \u057a\u0561\u057f\u0561\u0574\u0565\u0574"
        result = classify_text_classification(text)
        self.assertEqual(result.get("label"), "likely_western")

