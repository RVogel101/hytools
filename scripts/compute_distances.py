#!/usr/bin/env python
"""Compute multiple distance metrics between two texts or pairs listed in a CSV.

Metrics provided:
- char_edit_distance (Levenshtein)
- normalized_edit_distance (edit / max_len)
- token_jaccard (set Jaccard)
- js_divergence (Jensen-Shannon on token distributions)
- cosine_similarity (TF vectors)
- phonetic_edit_distance (edit on IPA/phonetic transcription)

Usage (pair of files):
  python scripts/compute_distances.py --a path/to/a.txt --b path/to/b.txt --out analysis/distances.csv

Usage (CSV of pairs):
  CSV must have columns: pair,text_a,text_b
  python scripts/compute_distances.py --csv path/to/pairs.csv --out analysis/distances.csv

"""
from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

from hytools.cleaning.armenian_tokenizer import extract_words
from hytools.linguistics import get_phonetic_transcription


def levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalized_edit(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 0.0
    ed = levenshtein(s1, s2)
    mx = max(1, len(s1), len(s2))
    return ed / mx


def token_jaccard(s1: str, s2: str) -> float:
    w1 = set(extract_words(s1, min_length=1))
    w2 = set(extract_words(s2, min_length=1))
    if not w1 and not w2:
        return 1.0
    inter = w1 & w2
    uni = w1 | w2
    return len(inter) / len(uni) if uni else 0.0


def js_divergence(s1: str, s2: str) -> float:
    # Jensen-Shannon divergence of token distributions (base e)
    def dist(tokens: Iterable[str]) -> Dict[str, float]:
        c = Counter(tokens)
        total = sum(c.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in c.items()}

    p = dist(extract_words(s1, min_length=1))
    q = dist(extract_words(s2, min_length=1))
    vocab = set(p.keys()) | set(q.keys())
    m = {w: 0.5 * (p.get(w, 0.0) + q.get(w, 0.0)) for w in vocab}

    def kl(a: Dict[str, float], b: Dict[str, float]) -> float:
        s = 0.0
        for w, pv in a.items():
            qv = b.get(w, 1e-12)
            if pv > 0:
                s += pv * math.log(pv / qv)
        return s

    if not vocab:
        return 0.0
    return 0.5 * (kl(p, m) + kl(q, m))


def cosine_similarity(s1: str, s2: str) -> float:
    v1 = Counter(extract_words(s1, min_length=1))
    v2 = Counter(extract_words(s2, min_length=1))
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[w] * v2[w] for w in common)
    norm1 = math.sqrt(sum(v * v for v in v1.values()))
    norm2 = math.sqrt(sum(v * v for v in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def phonetic_distance(s1: str, s2: str) -> int:
    t1 = get_phonetic_transcription(s1)
    t2 = get_phonetic_transcription(s2)
    return levenshtein(t1, t2)


def compute_all(s1: str, s2: str) -> Dict[str, float]:
    return {
        "char_edit_distance": levenshtein(s1, s2),
        "normalized_edit_distance": normalized_edit(s1, s2),
        "token_jaccard": token_jaccard(s1, s2),
        "js_divergence": js_divergence(s1, s2),
        "cosine_similarity": cosine_similarity(s1, s2),
        "phonetic_edit_distance": phonetic_distance(s1, s2),
    }


def process_pair_files(a_path: str, b_path: str) -> Tuple[str, str, Dict[str, float]]:
    a = open(a_path, "r", encoding="utf-8").read()
    b = open(b_path, "r", encoding="utf-8").read()
    metrics = compute_all(a, b)
    return a_path, b_path, metrics


def process_csv(input_csv: str) -> List[Tuple[str, str, Dict[str, float]]]:
    out = []
    with open(input_csv, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for rec in r:
            a = rec.get("text_a") or rec.get("a") or rec.get("text1")
            b = rec.get("text_b") or rec.get("b") or rec.get("text2")
            pair = rec.get("pair") or rec.get("name") or "pair"
            if not a or not b:
                continue
            a_path = a
            b_path = b
            _, _, metrics = process_pair_files(a_path, b_path)
            out.append((pair, f"{a_path}||{b_path}", metrics))
    return out


def write_results(out_path: str, rows: Iterable[Tuple[str, str, Dict[str, float]]]):
    fieldnames = [
        "pair",
        "files",
        "char_edit_distance",
        "normalized_edit_distance",
        "token_jaccard",
        "js_divergence",
        "cosine_similarity",
        "phonetic_edit_distance",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for pair, files, metrics in rows:
            row = {"pair": pair, "files": files}
            row.update(metrics)
            w.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Compute multiple distance metrics between texts")
    parser.add_argument("--a", help="Path to text A")
    parser.add_argument("--b", help="Path to text B")
    parser.add_argument("--csv", help="CSV of pairs with columns text_a,text_b")
    parser.add_argument("--out", default="analysis/wa_ea_pairwise_distances.csv", help="Output CSV")
    args = parser.parse_args()

    rows = []
    if args.csv:
        rows = process_csv(args.csv)
    elif args.a and args.b:
        a_path, b_path, metrics = process_pair_files(args.a, args.b)
        rows = [(f"{a_path} vs {b_path}", f"{a_path}||{b_path}", metrics)]
    else:
        parser.error("Provide --csv or both --a and --b")

    write_results(args.out, rows)
    print("Wrote results to", args.out)


if __name__ == "__main__":
    main()
