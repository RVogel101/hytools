from __future__ import annotations

import re
from typing import Tuple

# Minimal rule set derived from analysis/wa_ea_orthography_rules.yaml
CLASSICAL_TO_REFORM = [
    (r'իւ', 'յու'),
    (r'եան', 'յան'),
    (r'ութիւն', 'ություն'),
    (r'եւ', 'և'),
    (r'ւ', 'վ'),
]


def to_reformed(text: str) -> str:
    out = text
    for pat, rep in CLASSICAL_TO_REFORM:
        out = re.sub(pat, rep, out)
    return out


def to_classical(text: str) -> str:
    # Simple reverse mapping — note: ambiguous in some cases
    out = text
    for pat, rep in CLASSICAL_TO_REFORM:
        # swap rep -> pat (escape rep for regex)
        out = re.sub(re.escape(rep), pat, out)
    return out


def orthography_marker_counts(text: str) -> Tuple[int, int]:
    """Return (classical_marker_count, reformed_marker_count) for text."""
    classical_patterns = [r'իւ', r'եան', r'ուտյուն', r'եւ', r'ւ']
    reformed_patterns = [r'յու', r'յան', r'ություն', r'և', r'վ']

    classical_count = sum(len(re.findall(p, text)) for p in classical_patterns)
    reformed_count = sum(len(re.findall(p, text)) for p in reformed_patterns)
    return classical_count, reformed_count


def orthography_score(text: str) -> float:
    """Score in [0..1] where 1 = strongly classical, 0 = strongly reformed.

    Computed as classical_count / (classical_count + reformed_count)
    """
    c, r = orthography_marker_counts(text)
    if c + r == 0:
        return 0.5
    return c / (c + r)
