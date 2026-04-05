"""Western Armenian linguistic tools — phonology, morphology, lexicon, dialect, metrics.

All subpackages and symbols are lazy-loaded on first access.
Backward-compat sys.modules aliases are registered when the relevant
subpackage is actually imported.
"""

import importlib as _importlib
import sys as _sys

_SUBPACKAGES = ["phonology", "morphology", "lexicon", "dialect", "metrics"]

# Map of public symbol → (subpackage.module, symbol_name)
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Phonetics
    "ARMENIAN_PHONEMES": ("phonology.phonetics", "ARMENIAN_PHONEMES"),
    "ARMENIAN_DIGRAPHS": ("phonology.phonetics", "ARMENIAN_DIGRAPHS"),
    "LETTER_NAME_ARMENIAN": ("phonology.phonetics", "LETTER_NAME_ARMENIAN"),
    "LETTER_NAME_IPA": ("phonology.phonetics", "LETTER_NAME_IPA"),
    "LETTER_SOUND_IPA": ("phonology.phonetics", "LETTER_SOUND_IPA"),
    "LETTER_SOUND_IPA_WORD_INITIAL": ("phonology.phonetics", "LETTER_SOUND_IPA_WORD_INITIAL"),
    "is_vowel": ("phonology.phonetics", "is_vowel"),
    "get_phoneme_info": ("phonology.phonetics", "get_phoneme_info"),
    "get_phonetic_transcription": ("phonology.phonetics", "get_phonetic_transcription"),
    "calculate_phonetic_difficulty": ("phonology.phonetics", "calculate_phonetic_difficulty"),
    "get_pronunciation_guide": ("phonology.phonetics", "get_pronunciation_guide"),
    # Dialect
    "DialectClassification": ("dialect.branch_dialect_classifier", "DialectClassification"),
    # Stemmer
    "get_all_lemmas": ("morphology.stemmer", "get_all_lemmas"),
    "get_root_alternants": ("morphology.stemmer", "get_root_alternants"),
    "match_word_with_stemming": ("morphology.stemmer", "match_word_with_stemming"),
    # Loanword
    "LoanwordReport": ("lexicon.loanword_tracker", "LoanwordReport"),
    "PossibleLoanwordReport": ("lexicon.loanword_tracker", "PossibleLoanwordReport"),
    "analyze_loanwords": ("lexicon.loanword_tracker", "analyze_loanwords"),
    "analyze_possible_loanwords": ("lexicon.loanword_tracker", "analyze_possible_loanwords"),
    "analyze_batch": ("lexicon.loanword_tracker", "analyze_batch"),
    "get_loanword_lexicon": ("lexicon.loanword_tracker", "get_loanword_lexicon"),
    # Transliteration
    "Dialect": ("tools.transliteration", "Dialect"),
    "ASPIRATE": ("tools.transliteration", "ASPIRATE"),
    "to_latin": ("tools.transliteration", "to_latin"),
    "to_armenian": ("tools.transliteration", "to_armenian"),
    "to_ipa": ("tools.transliteration", "to_ipa"),
    "get_armenian_to_latin_map": ("tools.transliteration", "get_armenian_to_latin_map"),
    "get_latin_to_armenian_map": ("tools.transliteration", "get_latin_to_armenian_map"),
    "get_armenian_to_ipa_map": ("tools.transliteration", "get_armenian_to_ipa_map"),
}

__all__ = list(_LAZY_IMPORTS.keys()) + _SUBPACKAGES

# ---- Eager backward-compat sys.modules aliases ----
# Python 3.10 does NOT call __getattr__ for submodule imports like
# ``from hytools.linguistics.phonetics import X``.  We must register
# these aliases eagerly so that existing code keeps working.
_COMPAT_EAGER = {
    f"{__name__}.phonetics": ".phonology.phonetics",
    f"{__name__}.letter_data": ".phonology.letter_data",
    f"{__name__}.dialect_classifier": ".dialect.branch_dialect_classifier",
    f"{__name__}.loanword_tracker": ".lexicon.loanword_tracker",
}
for _alias, _rel in _COMPAT_EAGER.items():
    if _alias not in _sys.modules:
        try:
            _sys.modules[_alias] = _importlib.import_module(_rel, __name__)
        except ImportError:
            pass
del _alias, _rel  # clean up loop vars


def __getattr__(name: str):
    if name in _SUBPACKAGES:
        return _importlib.import_module(f".{name}", __name__)
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_path}", __name__)
        return getattr(mod, attr_name)
    # Backward-compat: loanword_tracker module object
    if name == "loanword_tracker":
        return _importlib.import_module(".lexicon.loanword_tracker", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
