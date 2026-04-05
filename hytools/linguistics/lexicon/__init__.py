"""Lexicon and etymology: loanword detection, etymology storage (MongoDB)."""

import importlib as _importlib

_SUBMODULES = ["etymology_db", "loanword_tracker"]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "LoanwordReport": ("loanword_tracker", "LoanwordReport"),
    "PossibleLoanwordReport": ("loanword_tracker", "PossibleLoanwordReport"),
    "analyze_loanwords": ("loanword_tracker", "analyze_loanwords"),
    "analyze_possible_loanwords": ("loanword_tracker", "analyze_possible_loanwords"),
    "analyze_batch": ("loanword_tracker", "analyze_batch"),
    "get_loanword_lexicon": ("loanword_tracker", "get_loanword_lexicon"),
    "add_loanwords": ("loanword_tracker", "add_loanwords"),
    "normalize_lexicon_word": ("loanword_tracker", "normalize_lexicon_word"),
    "SOURCE_WIKTIONARY": ("etymology_db", "SOURCE_WIKTIONARY"),
    "SOURCE_NAYIRI": ("etymology_db", "SOURCE_NAYIRI"),
    "SOURCE_MANUAL": ("etymology_db", "SOURCE_MANUAL"),
    "normalize_lemma": ("etymology_db", "normalize_lemma"),
    "import_etymology_from_wiktextract": ("etymology_db", "import_etymology_from_wiktextract"),
}

__all__ = _SUBMODULES + list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _SUBMODULES:
        return _importlib.import_module(f".{name}", __name__)
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
