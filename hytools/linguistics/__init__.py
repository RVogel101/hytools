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
dialect_classifier = dialect.branch_dialect_classifier
for _name, _mod in [
    ("linguistics.phonetics", phonetics),
    ("linguistics.letter_data", letter_data),
    ("linguistics.dialect_classifier", dialect_classifier),
]:
    if _name not in sys.modules:
        sys.modules[_name] = _mod

# Also register fully-qualified names for backwards compatibility (hytools package importers)
for _name, _mod in [
    ("hytools.linguistics.phonetics", phonetics),
    ("hytools.linguistics.letter_data", letter_data),
    ("hytools.linguistics.dialect_classifier", dialect_classifier),
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
from .dialect.branch_dialect_classifier import (
    DialectClassification,
)
from .morphology.stemmer import get_all_lemmas, get_root_alternants, match_word_with_stemming
from .lexicon.loanword_tracker import (
    LoanwordReport,
    PossibleLoanwordReport,
    analyze_loanwords,
    analyze_possible_loanwords,
    analyze_batch,
    get_loanword_lexicon,
)

# Backwards-compat: expose the loanword_tracker module object as
# `hytools.linguistics.loanword_tracker` so imports like
# `from hytools.linguistics.loanword_tracker import ...` continue to work.
from .lexicon import loanword_tracker as _loanword_tracker_mod
if "hytools.linguistics.loanword_tracker" not in sys.modules:
    sys.modules["hytools.linguistics.loanword_tracker"] = _loanword_tracker_mod
loanword_tracker = _loanword_tracker_mod
from .tools.transliteration import (
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
    # Dialect classification (datatypes only; functions moved to ingestion helpers)
    "DialectClassification",
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
