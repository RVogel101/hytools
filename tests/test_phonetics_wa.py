"""
Tests for Western Armenian phonetics (linguistics/phonetics.py).

Verifies WA voicing reversal, affricates (ձ=ts, ծ=dz, ջ=ch, ճ=j), and test words.
See docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md.
"""

import unittest

from hytools.linguistics.phonetics import (
    ARMENIAN_PHONEMES,
    get_phoneme_info,
    get_phonetic_transcription,
)


class TestWesternArmenianVoicingReversal(unittest.TestCase):
    """Verify voicing-reversed pairs are correct for Western Armenian."""

    def test_b_p_reversed(self):
        """բ=p, պ=b (reversed from Eastern)."""
        self.assertEqual(ARMENIAN_PHONEMES["բ"]["ipa"], "p")
        self.assertEqual(ARMENIAN_PHONEMES["պ"]["ipa"], "b")

    def test_d_t_reversed(self):
        """դ=t, տ=d (reversed from Eastern)."""
        self.assertEqual(ARMENIAN_PHONEMES["դ"]["ipa"], "t")
        self.assertEqual(ARMENIAN_PHONEMES["տ"]["ipa"], "d")

    def test_g_k_reversed(self):
        """գ=k, կ=g (reversed from Eastern)."""
        self.assertEqual(ARMENIAN_PHONEMES["գ"]["ipa"], "k")
        self.assertEqual(ARMENIAN_PHONEMES["կ"]["ipa"], "g")

    def test_ch_j_reversed(self):
        """ճ=j (dʒ), ջ=ch (tʃ) (reversed from Eastern)."""
        self.assertEqual(ARMENIAN_PHONEMES["ճ"]["ipa"], "dʒ")
        self.assertEqual(ARMENIAN_PHONEMES["ջ"]["ipa"], "tʃ")

    def test_dz_ts_reversed(self):
        """ձ=ts, ծ=dz (reversed from Eastern)."""
        self.assertEqual(ARMENIAN_PHONEMES["ձ"]["ipa"], "ts")
        self.assertEqual(ARMENIAN_PHONEMES["ծ"]["ipa"], "dz")

    def test_theta_not_th(self):
        """թ=t (not English th)."""
        self.assertEqual(ARMENIAN_PHONEMES["թ"]["ipa"], "t")


class TestWesternArmenianVerificationWords(unittest.TestCase):
    """Verify canonical WA test words produce correct transcriptions."""

    def test_petk_bedk(self):
        """պետք → bedk (Western)."""
        info = get_phonetic_transcription("պետք")
        approx = info["english_approx"].lower()
        self.assertIn("b", approx, "պ must be b not p")
        self.assertIn("d", approx, "տ must be d not t")

    def test_joor_choor(self):
        """ջուր → choor (Western)."""
        info = get_phoneme_info("ջ")
        self.assertEqual(info["english"], "ch")

    def test_voch(self):
        """ոչ → voch (ո before consonant = vo)."""
        info = get_phoneme_info("ո")
        self.assertIn("v", info["english"].lower())
