"""Quantitative dialect distance models for Western vs Eastern Armenian.

This module provides a component-based framework to compare two corpora:
1. Lexical differences (word usage, distributional divergence, mapping drift)
2. Structural differences (sentence-length profile, function-word bigrams)

The output is a weighted, interpretable score with per-component metrics,
so you can audit where WA/EA divergence comes from.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from armenian_corpus_core.cleaning.armenian_tokenizer import extract_words

_SENT_SPLIT_RE = re.compile(r"(?<=[։.!?])\s+")


@dataclass
class DistanceWeights:
    """Weights for component and sub-component aggregation."""

    lexical_weight: float = 0.65
    structural_weight: float = 0.35

    lexical_subweights: dict[str, float] = field(
        default_factory=lambda: {
            "js_divergence": 0.40,
            "weighted_jaccard_distance": 0.25,
            "mapping_shift_rate": 0.15,
            "variant_usage_rate_distance": 0.20,
            "keyword_context_js": 0.00,
        }
    )
    structural_subweights: dict[str, float] = field(
        default_factory=lambda: {
            "sentence_length_wasserstein": 0.60,
            "function_bigram_js": 0.40,
        }
    )


@dataclass
class DistanceReport:
    """Interpretable report for component-based dialect distance."""

    lexical_metrics: dict[str, float]
    structural_metrics: dict[str, float]
    lexical_component: float
    structural_component: float
    total_distance: float


def _safe_normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(v, 0.0) for v in weights.values())
    if total <= 0:
        # Fall back to equal weights.
        n = max(len(weights), 1)
        return {k: 1.0 / n for k in weights}
    return {k: max(v, 0.0) / total for k, v in weights.items()}


def _to_probability(counter: Counter) -> dict[str, float]:
    total = sum(counter.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in counter.items() if v > 0}


def jensen_shannon_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Compute Jensen-Shannon divergence in [0, 1] using log base 2."""
    keys = set(p) | set(q)
    if not keys:
        return 0.0

    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a: dict[str, float], b: dict[str, float]) -> float:
        out = 0.0
        for k, av in a.items():
            if av <= 0:
                continue
            bv = b.get(k, 0.0)
            if bv <= 0:
                continue
            out += av * math.log2(av / bv)
        return out

    js = 0.5 * kl(p, m) + 0.5 * kl(q, m)
    return float(max(0.0, min(js, 1.0)))


def hellinger_distance(p: dict[str, float], q: dict[str, float]) -> float:
    """Compute Hellinger distance in [0, 1]."""
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    sq = sum((math.sqrt(p.get(k, 0.0)) - math.sqrt(q.get(k, 0.0))) ** 2 for k in keys)
    return float(max(0.0, min(math.sqrt(sq) / math.sqrt(2.0), 1.0)))


def cosine_distance(p: dict[str, float], q: dict[str, float]) -> float:
    """Compute cosine distance (1 - cosine similarity) in [0, 1]."""
    keys = set(p) | set(q)
    if not keys:
        return 0.0

    dot = sum(p.get(k, 0.0) * q.get(k, 0.0) for k in keys)
    np = math.sqrt(sum(v * v for v in p.values()))
    nq = math.sqrt(sum(v * v for v in q.values()))
    if np <= 0 or nq <= 0:
        return 1.0
    sim = dot / (np * nq)
    sim = max(0.0, min(sim, 1.0))
    dist = 1.0 - sim
    if abs(dist) < 1e-12:
        return 0.0
    return dist


def weighted_jaccard_distance(c1: Counter, c2: Counter) -> float:
    """Weighted Jaccard distance for count vectors, in [0, 1]."""
    keys = set(c1) | set(c2)
    if not keys:
        return 0.0
    num = sum(min(c1.get(k, 0), c2.get(k, 0)) for k in keys)
    den = sum(max(c1.get(k, 0), c2.get(k, 0)) for k in keys)
    if den <= 0:
        return 0.0
    return 1.0 - (num / den)


def wasserstein_1d(samples_a: list[int], samples_b: list[int]) -> float:
    """Approximate 1D Wasserstein-1 distance via empirical CDFs."""
    if not samples_a and not samples_b:
        return 0.0
    if not samples_a or not samples_b:
        return 1.0

    a = sorted(samples_a)
    b = sorted(samples_b)
    vals = sorted(set(a) | set(b))

    def cdf(x: int, arr: list[int]) -> float:
        lo, hi = 0, len(arr)
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] <= x:
                lo = mid + 1
            else:
                hi = mid
        return lo / len(arr)

    area = 0.0
    prev = vals[0]
    for x in vals[1:]:
        diff = abs(cdf(prev, a) - cdf(prev, b))
        area += diff * (x - prev)
        prev = x

    # Normalize by max observed span for [0,1]-ish comparability.
    span = max(vals[-1] - vals[0], 1)
    return min(area / span, 1.0)


def _split_sentences(text: str) -> list[str]:
    parts = _SENT_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _extract_function_bigrams(tokens: list[str], function_words: set[str]) -> Counter:
    seq = [tok for tok in tokens if tok in function_words]
    return Counter((seq[i], seq[i + 1]) for i in range(len(seq) - 1))


def _mapping_shift_rate(tokens: list[str], west_east_mapping: dict[str, dict] | None) -> float:
    """Share of tokens matching Eastern forms from the mapping."""
    if not tokens or not west_east_mapping:
        return 0.0
    eastern_forms = set(west_east_mapping.keys())
    hits = sum(1 for t in tokens if t in eastern_forms)
    return hits / len(tokens)


def _variant_usage_rate_distance(
    west_counts: Counter,
    east_counts: Counter,
    variant_pairs: list[tuple[str, str]],
) -> float:
    """Measure preference shifts between WA/EA variant pairs.

    Each pair is ``(western_form, eastern_form)``. The metric compares
    how strongly each corpus prefers one form over the other:

    ``preference = west_form / (west_form + east_form)``

    and aggregates ``|preference_west_corpus - preference_east_corpus|``
    weighted by pair support.
    """
    if not variant_pairs:
        return 0.0

    alpha = 1.0  # Laplace smoothing for low-frequency pairs
    weighted_sum = 0.0
    total_weight = 0.0

    for west_form, east_form in variant_pairs:
        w_w = west_counts.get(west_form, 0)
        w_e = west_counts.get(east_form, 0)
        e_w = east_counts.get(west_form, 0)
        e_e = east_counts.get(east_form, 0)

        pref_west = (w_w + alpha) / (w_w + w_e + 2 * alpha)
        pref_east = (e_w + alpha) / (e_w + e_e + 2 * alpha)
        pair_distance = abs(pref_west - pref_east)

        # Support weight emphasizes pairs with real signal in either corpus.
        support = w_w + w_e + e_w + e_e
        weight = math.log1p(support)
        if weight <= 0:
            continue

        weighted_sum += weight * pair_distance
        total_weight += weight

    if total_weight <= 0:
        return 0.0
    return weighted_sum / total_weight


def _keyword_context_divergence(
    west_tokens: list[str],
    east_tokens: list[str],
    keywords: list[str],
    window: int = 2,
) -> float:
    """Compare context distributions for shared keywords across corpora.

    For each keyword, build a neighboring-word distribution (windowed) in each
    corpus and compute JS divergence. Returns support-weighted average.
    """
    if not keywords:
        return 0.0

    def build_context(tokens: list[str], keyword: str) -> Counter:
        ctx: Counter = Counter()
        for i, tok in enumerate(tokens):
            if tok != keyword:
                continue
            lo = max(0, i - window)
            hi = min(len(tokens), i + window + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                ctx[tokens[j]] += 1
        return ctx

    weighted_sum = 0.0
    total_weight = 0.0

    for kw in keywords:
        west_ctx = build_context(west_tokens, kw)
        east_ctx = build_context(east_tokens, kw)
        west_hits = west_tokens.count(kw)
        east_hits = east_tokens.count(kw)
        support = west_hits + east_hits
        if support <= 1:
            continue

        js = jensen_shannon_divergence(_to_probability(west_ctx), _to_probability(east_ctx))
        weight = math.log1p(support)
        weighted_sum += weight * js
        total_weight += weight

    if total_weight <= 0:
        return 0.0
    return weighted_sum / total_weight


def compute_component_distance(
    western_texts: Iterable[str],
    eastern_texts: Iterable[str],
    *,
    west_east_mapping: dict[str, dict] | None = None,
    variant_pairs: list[tuple[str, str]] | None = None,
    contextual_keywords: list[str] | None = None,
    function_words: set[str] | None = None,
    weights: DistanceWeights | None = None,
) -> DistanceReport:
    """Compute a component-based WA/EA distance score.

    Parameters
    ----------
    western_texts:
        Iterable of texts representing the Western corpus/sample.
    eastern_texts:
        Iterable of texts representing the Eastern corpus/sample.
    west_east_mapping:
        Optional mapping from `CorpusVocabularyBuilder.build_west_east_usage_mapping`.
    function_words:
        Optional function-word list for structure-sensitive bigram distance.
    weights:
        Optional custom aggregation weights.
    """
    cfg = weights or DistanceWeights()
    lex_w = _safe_normalize(cfg.lexical_subweights)
    str_w = _safe_normalize(cfg.structural_subweights)

    west_joined = "\n".join(western_texts)
    east_joined = "\n".join(eastern_texts)

    west_tokens = extract_words(west_joined, min_length=2)
    east_tokens = extract_words(east_joined, min_length=2)

    west_counts = Counter(west_tokens)
    east_counts = Counter(east_tokens)

    west_prob = _to_probability(west_counts)
    east_prob = _to_probability(east_counts)

    js = jensen_shannon_divergence(west_prob, east_prob)
    wj = weighted_jaccard_distance(west_counts, east_counts)
    shift = _mapping_shift_rate(east_tokens, west_east_mapping)

    if variant_pairs is None and west_east_mapping:
        auto_pairs: list[tuple[str, str]] = []
        for east_form, meta in west_east_mapping.items():
            west_form = str(meta.get("canonical_western_form", "")).strip()
            if west_form:
                auto_pairs.append((west_form, east_form))
        variant_pairs = auto_pairs
    variant_pairs = variant_pairs or []

    variant_rate_dist = _variant_usage_rate_distance(west_counts, east_counts, variant_pairs)
    keyword_context_js = _keyword_context_divergence(
        west_tokens,
        east_tokens,
        contextual_keywords or [],
    )

    lexical_metrics = {
        "js_divergence": js,
        "weighted_jaccard_distance": wj,
        "mapping_shift_rate": shift,
        "variant_usage_rate_distance": variant_rate_dist,
        "keyword_context_js": keyword_context_js,
        # Extra model outputs for comparison/ablation
        "hellinger_distance": hellinger_distance(west_prob, east_prob),
        "cosine_distance": cosine_distance(west_prob, east_prob),
    }

    west_sentence_lengths = [len(extract_words(s, min_length=1)) for s in _split_sentences(west_joined)]
    east_sentence_lengths = [len(extract_words(s, min_length=1)) for s in _split_sentences(east_joined)]
    sent_w1 = wasserstein_1d(west_sentence_lengths, east_sentence_lengths)

    fn_words = function_words or set()
    west_fn_bi = _extract_function_bigrams(west_tokens, fn_words)
    east_fn_bi = _extract_function_bigrams(east_tokens, fn_words)
    fn_js = jensen_shannon_divergence(_to_probability(west_fn_bi), _to_probability(east_fn_bi))

    structural_metrics = {
        "sentence_length_wasserstein": sent_w1,
        "function_bigram_js": fn_js,
    }

    lexical_component = (
        lex_w.get("js_divergence", 0.0) * lexical_metrics["js_divergence"]
        + lex_w.get("weighted_jaccard_distance", 0.0) * lexical_metrics["weighted_jaccard_distance"]
        + lex_w.get("mapping_shift_rate", 0.0) * lexical_metrics["mapping_shift_rate"]
        + lex_w.get("variant_usage_rate_distance", 0.0) * lexical_metrics["variant_usage_rate_distance"]
        + lex_w.get("keyword_context_js", 0.0) * lexical_metrics["keyword_context_js"]
    )

    structural_component = (
        str_w.get("sentence_length_wasserstein", 0.0) * structural_metrics["sentence_length_wasserstein"]
        + str_w.get("function_bigram_js", 0.0) * structural_metrics["function_bigram_js"]
    )

    # Normalize top-level component weights to keep score in [0,1]-ish range.
    top = _safe_normalize(
        {
            "lexical": cfg.lexical_weight,
            "structural": cfg.structural_weight,
        }
    )

    total = top["lexical"] * lexical_component + top["structural"] * structural_component

    return DistanceReport(
        lexical_metrics=lexical_metrics,
        structural_metrics=structural_metrics,
        lexical_component=lexical_component,
        structural_component=structural_component,
        total_distance=total,
    )
