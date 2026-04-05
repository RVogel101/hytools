"""Armenian morphology sub-package."""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ARM": ("core", "ARM"),
    "VOWELS": ("core", "VOWELS"),
    "is_vowel": ("core", "is_vowel"),
    "ends_in_vowel": ("core", "ends_in_vowel"),
    "decline_noun": ("nouns", "decline_noun"),
    "NounDeclension": ("nouns", "NounDeclension"),
    "DECLENSION_CLASSES": ("nouns", "DECLENSION_CLASSES"),
    "conjugate_verb": ("verbs", "conjugate_verb"),
    "VerbConjugation": ("verbs", "VerbConjugation"),
    "VERB_CLASSES": ("verbs", "VERB_CLASSES"),
    "add_definite": ("articles", "add_definite"),
    "add_indefinite": ("articles", "add_indefinite"),
    "detect_verb_class": ("detect", "detect_verb_class"),
    "detect_noun_class": ("detect", "detect_noun_class"),
    "detect_pos_and_class": ("detect", "detect_pos_and_class"),
    "get_irregular_overrides": ("irregular_verbs", "get_irregular_overrides"),
    "is_irregular": ("irregular_verbs", "is_irregular"),
    "list_irregular_infinitives": ("irregular_verbs", "list_irregular_infinitives"),
    "count_syllables_with_context": ("difficulty", "count_syllables_with_context"),
    "score_word_difficulty": ("difficulty", "score_word_difficulty"),
    "WordDifficultyAnalysis": ("difficulty", "WordDifficultyAnalysis"),
    "analyze_word": ("difficulty", "analyze_word"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
