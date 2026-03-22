"""Western Armenian linguistic tools — phonology, morphology, lexicon, dialect, metrics."""

import sys

# Subpackages (Option B layout)
from . import phonology
from . import morphology
from . import lexicon
from . import dialect
from . import metrics

# Backward-compat: register so "from hytools.linguistics.phonetics import ..." resolves
phonetics = phonology.phonetics
letter_data = phonology.letter_data
dialect_classifier = dialect.dialect_classifier
loanword_tracker = lexicon.loanword_tracker
etymology_db = lexicon.etymology_db
for _name, _mod in [
    ("linguistics.phonetics", phonetics),
    ("linguistics.letter_data", letter_data),
    ("linguistics.dialect_classifier", dialect_classifier),
    ("linguistics.loanword_tracker", loanword_tracker),
    ("linguistics.etymology_db", etymology_db),
]:
    if _name not in sys.modules:
        sys.modules[_name] = _mod

# Re-export main API from subpackages
from .phonology.phonetics import (
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
from .dialect.dialect_classifier import (
    DialectClassification,
    classify_text_dialect,
    classify_batch_texts,
    classify_vocab_and_sentences,
)
from .stemmer import get_all_lemmas, get_root_alternants, match_word_with_stemming
from .lexicon.loanword_tracker import (
    LoanwordReport,
    PossibleLoanwordReport,
    analyze_loanwords,
    analyze_possible_loanwords,
    analyze_batch,
    get_loanword_lexicon,
)
from .transliteration import (
    Dialect,
    ASPIRATE,
    to_latin,
    to_armenian,
    to_ipa,
    get_armenian_to_latin_map,
    get_latin_to_armenian_map,
    get_armenian_to_ipa_map,
)

__all__ = [
    # Phonetics (phonology)
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
    "get_root_alternants",
    "match_word_with_stemming",
    # Loanword tracking
    "LoanwordReport",
    "PossibleLoanwordReport",
    "analyze_loanwords",
    "analyze_possible_loanwords",
    "analyze_batch",
    "get_loanword_lexicon",
    # Transliteration (BGN/PCGN + IPA)
    "Dialect",
    "ASPIRATE",
    "to_latin",
    "to_armenian",
    "to_ipa",
    "get_armenian_to_latin_map",
    "get_latin_to_armenian_map",
    "get_armenian_to_ipa_map",
    # Subpackages
    "morphology",
    "phonology",
    "lexicon",
    "dialect",
    "metrics",
]
