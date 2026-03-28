from __future__ import annotations

import re
from statistics import mean, median, stdev
from typing import Iterable, List, Tuple

from hytools.linguistics.phonology.phonetics import get_phonetic_transcription


SENTENCE_SPLIT_RE = re.compile(r'[։?!:\n]+')


def normalize_phonetic_output(obj) -> str:
    """Normalize output of get_phonetic_transcription to a plain string.

    Handles lists, tuples, dicts, or strings.
    """
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return " ".join(str(x) for x in obj)
    if isinstance(obj, dict):
        # prefer 'ipa' field when available
        if 'ipa' in obj:
            return str(obj['ipa'])
        return " ".join(str(v) for v in obj.values())
    return str(obj)


def phonetic_transcription(text: str, dialect: str = "hye-w") -> str:
    # underlying get_phonetic_transcription currently supports only a single-arg word
    out = get_phonetic_transcription(text)
    return normalize_phonetic_output(out)


def split_sentences(text: str) -> List[str]:
    parts = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return parts


def align_sentences(sentences_a: List[str], sentences_b: List[str]) -> List[Tuple[str, str]]:
    """Length-based dynamic programming alignment (monotonic).

    Aligns two sentence sequences using dynamic programming with a cost
    proportional to the absolute difference in sentence lengths. Returns
    a list of matched (a,b) sentence pairs where both sides are present
    (1-1 alignments). This is a simple, robust alternative to naive
    index-based pairing. It does not produce 1-to-many merges.
    """
    la = [len(s) for s in sentences_a]
    lb = [len(s) for s in sentences_b]
    na = len(la)
    nb = len(lb)

    # DP table: cost to align prefixes
    import math

    dp = [[math.inf] * (nb + 1) for _ in range(na + 1)]
    dp[0][0] = 0.0
    # backpointers
    back = [[None] * (nb + 1) for _ in range(na + 1)]

    for i in range(na + 1):
        for j in range(nb + 1):
            if i < na and j < nb:
                cost = abs(la[i] - lb[j])
                if dp[i + 1][j + 1] > dp[i][j] + cost:
                    dp[i + 1][j + 1] = dp[i][j] + cost
                    back[i + 1][j + 1] = (i, j)
            if i < na:
                # gap in B (skip A[i]) with penalty proportional to its length
                cost = la[i] * 0.5
                if dp[i + 1][j] > dp[i][j] + cost:
                    dp[i + 1][j] = dp[i][j] + cost
                    back[i + 1][j] = (i, j)
            if j < nb:
                # gap in A (skip B[j])
                cost = lb[j] * 0.5
                if dp[i][j + 1] > dp[i][j] + cost:
                    dp[i][j + 1] = dp[i][j] + cost
                    back[i][j + 1] = (i, j)

    # backtrace from (na, nb)
    i, j = na, nb
    matches: List[Tuple[int, int]] = []
    while i > 0 or j > 0:
        prev = back[i][j]
        if prev is None:
            break
        pi, pj = prev
        # if both advanced, it's a match
        if pi == i - 1 and pj == j - 1:
            matches.append((pi, pj))
        i, j = pi, pj

    matches.reverse()
    return [(sentences_a[a], sentences_b[b]) for a, b in matches]


def aggregate_numeric(values: Iterable[float]) -> dict:
    vals = list(values)
    if not vals:
        return {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0}
    return {
        "count": len(vals),
        "mean": mean(vals),
        "median": median(vals),
        "std": stdev(vals) if len(vals) > 1 else 0.0,
    }
