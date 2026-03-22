"""Compatibility module for hytools.linguistics.loanword_tracker."""

from .lexicon.loanword_tracker import *

__all__ = [
    "LoanwordReport",
    "PossibleLoanwordReport",
    "analyze_loanwords",
    "analyze_possible_loanwords",
    "analyze_batch",
    "get_loanword_lexicon",
]
