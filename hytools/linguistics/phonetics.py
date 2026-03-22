"""Compatibility module for hytools.linguistics.phonetics."""

from .phonology.phonetics import *

__all__ = [
    "ARMENIAN_PHONEMES",
    "ARMENIAN_DIGRAPHS",
    "LETTER_NAME_ARMENIAN",
    "LETTER_NAME_IPA",
    "LETTER_SOUND_IPA",
    "LETTER_SOUND_IPA_WORD_INITIAL",
    "is_vowel",
    "get_phoneme_info",
    "get_phonetic_transcription",
    "calculate_phonetic_difficulty",
    "get_pronunciation_guide",
]
