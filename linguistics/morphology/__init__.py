"""Armenian morphology sub-package."""

from .core import ARM, VOWELS, is_vowel, ends_in_vowel
from .nouns import decline_noun, NounDeclension, DECLENSION_CLASSES
from .verbs import conjugate_verb, VerbConjugation, VERB_CLASSES
from .articles import add_definite, add_indefinite
from .detect import detect_verb_class, detect_noun_class, detect_pos_and_class
from .irregular_verbs import get_irregular_overrides, is_irregular, list_irregular_infinitives
from .difficulty import (
    count_syllables_with_context,
    score_word_difficulty,
    WordDifficultyAnalysis,
    analyze_word,
)

__all__ = [
    "ARM", "VOWELS", "is_vowel", "ends_in_vowel",
    "decline_noun", "NounDeclension", "DECLENSION_CLASSES",
    "conjugate_verb", "VerbConjugation", "VERB_CLASSES",
    "add_definite", "add_indefinite",
    "detect_verb_class", "detect_noun_class", "detect_pos_and_class",
    "get_irregular_overrides", "is_irregular", "list_irregular_infinitives",
    "count_syllables_with_context",
    "score_word_difficulty",
    "WordDifficultyAnalysis",
    "analyze_word",
]
