"""Western Armenian linguistic tools — phonetics, morphology, FSRS, dialect classification."""

from .phonetics import (
    ARMENIAN_PHONEMES,
    ARMENIAN_DIGRAPHS,
    LETTER_NAME_ARMENIAN,
    LETTER_NAME_IPA,
    LETTER_SOUND_IPA,
    LETTER_SOUND_IPA_WORD_INITIAL,
    is_vowel,
    get_phoneme_info,
    get_phonetic_transcription,
    calculate_phonetic_difficulty,
    get_pronunciation_guide,
)
from .fsrs import DEFAULT_WEIGHTS, CardState, FSRSScheduler
from .dialect_classifier import (
    DialectClassification,
    classify_text_dialect,
    classify_batch_texts,
    classify_vocab_and_sentences,
)
from .stemmer import get_all_lemmas, match_word_with_stemming
from . import morphology

__all__ = [
    # Phonetics
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
    # FSRS
    "DEFAULT_WEIGHTS",
    "CardState",
    "FSRSScheduler",
    # Dialect classification
    "DialectClassification",
    "classify_text_dialect",
    "classify_batch_texts",
    "classify_vocab_and_sentences",
    # Stemmer
    "get_all_lemmas",
    "match_word_with_stemming",
    # Subpackages
    "morphology",
]
