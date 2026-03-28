#!/usr/bin/env python
"""Hyperparameter tuning for WA scoring rule weights.

Uses textbook WA/EA sentences for train/validation split. Computes best per-rule
weights by grid search over limited ranges, and prints before/after metrics.

Usage:
  python scripts/tune_wa_scoring.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Dict, List, Tuple

from hytools.ingestion._shared import helpers as h

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
SOURCE_PATH = Path(__file__).resolve().parent.parent / "tests" / "data" / "textbook_modern_wa_vocab_and_sentences.json"
RANDOM_SEED = 42
TRAIN_PCT = 0.8

# Rules for tuning (must match _CONSOLIDATED_RULES rule_id entries)
TUNABLE_RULES = {
    "WA_NEG_CONJUNCTION_AYL": (0.0, 3.0),
    "WA_PRESENT_ONSET_GU": (0.0, 3.0),
    "WA_CASE_DATIVE_WITHIN": (0.0, 2.5),
    "WA_VERB_PARTICIPLE_ALU": (0.0, 2.5),
    "WA_VOCAB_SHAD": (0.0, 2.0),
}

# Scoring threshold for likely_western
WA_SCORE_THRESHOLD = 5.0

# Grid settings
GRID_STEP = 0.5

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def load_data() -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
    with open(SOURCE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    west = [(t, 1) for t in data.get("sentences_western", [])]
    east = [(t, 0) for t in data.get("sentences_eastern", [])]
    return west, east


def split_data(items: List[Tuple[str, int]], seed: int = RANDOM_SEED) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
    random.Random(seed).shuffle(items)
    n_train = int(TRAIN_PCT * len(items))
    return items[:n_train], items[n_train:]


def classify_text(text: str) -> str:
    result = h.classify_text_classification(text)
    if result["label"] == "likely_western":
        return "western"
    if result["label"] == "likely_eastern":
        return "eastern"
    # for inconclusive use score threshold
    if h.compute_wa_score(text) >= WA_SCORE_THRESHOLD:
        return "western"
    return "eastern"


def score_dataset(dataset: List[Tuple[str, int]]) -> Dict[str, float]:
    tp = fp = fn = tn = 0
    for text, true_label in dataset:
        pred = classify_text(text)
        if true_label == 1:  # WA
            if pred == "western":
                tp += 1
            else:
                fn += 1
        else:  # EA
            if pred == "western":
                fp += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def set_weights(weights: Dict[str, float], base_weights: Dict[str, float]):
    # modify helpers consolidated rules in-place using base + tuned offsets
    for i, rule in enumerate(h._CONSOLIDATED_RULES):
        rule_id = rule.get("rule_id")
        if rule_id in weights:
            new_weight = max(0.0, base_weights.get(rule_id, rule.get("weight", 0.0)) + weights[rule_id])
            h._CONSOLIDATED_RULES[i] = {**rule, "weight": new_weight}
    h._CONSOLIDATED_COMPILED = [(r, re.compile(r["pattern"], flags=re.IGNORECASE)) for r in h._CONSOLIDATED_RULES]


def grid_search(train_data, valid_data):
    best = None
    best_metrics = None
    rule_ids = list(TUNABLE_RULES.keys())

    # record base weights so we apply offsets (tunable weights are deltas)
    base_weights = {r["rule_id"]: r["weight"] for r in h._CONSOLIDATED_RULES if r["rule_id"] in rule_ids}

    def float_range(start, stop, step):
        vals = []
        current = start
        while current <= stop + 1e-9:
            vals.append(round(current, 3))
            current += step
        return vals

    ranges = {r: float_range(lo, hi, GRID_STEP) for r, (lo, hi) in TUNABLE_RULES.items()}

    total = 1
    for r in rule_ids:
        total *= len(ranges[r])
    print(f"Grid search space size: {total} weight combinations")

    best = None
    best_metrics = None

    def recurse(rule_idx, current_weights):
        nonlocal best, best_metrics
        if rule_idx == len(rule_ids):
            set_weights(current_weights, base_weights)
            metrics = score_dataset(train_data)
            if best_metrics is None or metrics["f1"] > best_metrics["f1"]:
                best_metrics = metrics
                best = current_weights.copy()
            return
        rule = rule_ids[rule_idx]
        for val in ranges[rule]:
            current_weights[rule] = val
            recurse(rule_idx + 1, current_weights)

    recurse(0, {})
    # final evaluation on validation set
    set_weights(best, base_weights)
    valid_metrics = score_dataset(valid_data)
    return best, best_metrics, valid_metrics


if __name__ == "__main__":
    west, east = load_data()
    west_train, west_valid = split_data(west)
    east_train, east_valid = split_data(east)

    train_set = west_train + east_train
    valid_set = west_valid + east_valid

    print(f"train set {len(train_set)} sentences (WA={len(west_train)}, EA={len(east_train)})")
    print(f"valid set {len(valid_set)} sentences (WA={len(west_valid)}, EA={len(east_valid)})")

    best_w, train_m, valid_m = grid_search(train_set, valid_set)

    print("\n== Best weights ==")
    for k,v in best_w.items():
        print(f" {k}: {v}")
    print("\n== Train metrics ==")
    print(train_m)
    print("\n== Valid metrics ==")
    print(valid_m)
