"""
Tests for stemmer integration with monosyllabic root dictionary.

Root data: data/monosyllabic_roots.json from "200 Monosyllabic Words" (Fr. Ghevond Ajamian ©2015).
Verifies that root alternants (e.g. գիր/գր, սէր/սիր) are used for lemma expansion and matching.
"""

from __future__ import annotations

import unittest

from hytools.linguistics.stemmer import (
    get_all_lemmas,
    get_root_alternants,
    match_word_with_stemming,
)


class TestMonosyllabicRootAlternants(unittest.TestCase):
    def test_get_root_alternants_returns_group(self):
        # գիր/գր — writing (verb_ref: գրել)
        alt = get_root_alternants("գիր")
        self.assertIn("գիր", alt)
        self.assertIn("գր", alt)
        self.assertGreaterEqual(len(alt), 2)

    def test_get_root_alternants_symmetric(self):
        alt_gr = get_root_alternants("գր")
        alt_gir = get_root_alternants("գիր")
        self.assertEqual(alt_gr, alt_gir)

    def test_get_root_alternants_sir_ser(self):
        # սէր/սիր — love
        alt = get_root_alternants("սէր")
        self.assertIn("սէր", alt)
        self.assertIn("սիր", alt)

    def test_get_root_alternants_unknown_returns_empty(self):
        alt = get_root_alternants("ծծծ")
        self.assertEqual(alt, set())

    def test_get_root_alternants_normalizes_case(self):
        alt = get_root_alternants("ԳԻՐ")
        self.assertIn("գիր", alt)
        self.assertIn("գր", alt)


class TestGetAllLemmasIncludesRootAlternants(unittest.TestCase):
    def test_lemma_set_contains_alternant_when_word_is_root(self):
        lemmas = get_all_lemmas("գր")
        self.assertIn("գր", lemmas)
        self.assertIn("գիր", lemmas)

    def test_lemma_set_contains_alternant_for_sir(self):
        lemmas = get_all_lemmas("սիր")
        self.assertIn("սիր", lemmas)
        self.assertIn("սէր", lemmas)

    def test_match_vocab_root_to_corpus_alternant(self):
        # Corpus has "գր", vocab has "գիր" — should match via lemma
        corpus = {"գր", "տուն"}
        matched, match_type = match_word_with_stemming("գիր", corpus)
        self.assertTrue(matched, "գիր should match corpus 'գր' via root alternant")
        self.assertEqual(match_type, "lemma")

    def test_match_vocab_alternant_to_corpus_root(self):
        # Corpus has "սէր", vocab has "սիր" — should match via lemma
        corpus = {"սէր"}
        matched, match_type = match_word_with_stemming("սիր", corpus)
        self.assertTrue(matched)
        self.assertEqual(match_type, "lemma")


class TestMonosyllabicRootDataLoaded(unittest.TestCase):
    """Ensure data file is present and at least known roots are available."""

    def test_common_roots_have_alternants(self):
        # From the PDF: a few representative roots with alternants
        pairs = [
            ("գիր", "գր"),
            ("սէր", "սիր"),
            ("լոյս", "լուս"),
            ("բոյժ", "բուժ"),
            ("ձեռ", "ձեռն"),
        ]
        for a, b in pairs:
            with self.subTest(a=a, b=b):
                alt_a = get_root_alternants(a)
                self.assertIn(a, alt_a, f"Root {a} should be in its own alternant set")
                self.assertIn(b, alt_a, f"Alternant {b} should be in set for {a}")
