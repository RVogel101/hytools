"""Tests for linguistics.transliteration (to_latin, to_ipa, to_armenian)."""
from __future__ import annotations

import unittest

from linguistics.transliteration import to_armenian, to_latin


class TestWesternOysUy(unittest.TestCase):
    """Western: ոյ when not word-final → 'uy' in Latin (e.g. յոյս → huys). IPA unchanged."""

    def test_oys_non_final_to_uy(self):
        self.assertEqual(to_latin("յոյս", dialect="western"), "huys")

    def test_uy_reverse_to_oys(self):
        self.assertEqual(to_armenian("uy", dialect="western"), "ոյ")


class TestToArmenianWesternEvYev(unittest.TestCase):
    """Western: և only for 'and'; եւ in words."""

    def test_standalone_ev_becomes_yev(self):
        """Standalone token 'ev' → և (and)."""
        self.assertEqual(to_armenian("ev", dialect="western"), "և")
        self.assertEqual(to_armenian("  ev  ", dialect="western"), "և")

    def test_standalone_yev_becomes_yev(self):
        """Standalone token 'yev' → և (and)."""
        self.assertEqual(to_armenian("yev", dialect="western"), "և")

    def test_standalone_english_and_becomes_yev(self):
        """Standalone token 'and' → և (and)."""
        self.assertEqual(to_armenian("and", dialect="western"), "և")
        # Phrase: "and" as standalone word must become և
        result = to_armenian("bread and water", dialect="western")
        self.assertIn("և", result)
        self.assertNotIn("and", result)

    def test_in_word_ev_becomes_ew(self):
        """In-word 'ev' → եւ (two characters), not ligature և."""
        result = to_armenian("yevroke", dialect="western")  # եվրոկէ or similar
        self.assertIn("եւ", result)
        self.assertNotEqual(result, "ևրոկէ")  # should not be ligature in word

    def test_eastern_ev_remains_ligature(self):
        """Eastern keeps և for both 'and' and in-word ev/yev."""
        self.assertEqual(to_armenian("ev", dialect="eastern"), "և")
        self.assertEqual(to_armenian("yevroke", dialect="eastern").count("և"), 1)


if __name__ == "__main__":
    unittest.main()
