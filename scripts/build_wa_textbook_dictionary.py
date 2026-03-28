#!/usr/bin/env python
"""Build a WA textbook lexicon dataset from text files.

Generates `hytools/data/wa_textbook_dictionary.csv` with token frequency
and heuristic categories for particles, lexicon, morphological suffixes.
"""
from collections import Counter
from pathlib import Path
import csv
import re

INPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "textbook_modern_wa_pages"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "wa_textbook_dictionary.csv"

PARTICLES = {"կը", "մը", "պիտի", "չը", "կու", "ոչ"}
MORPH_SUFFIXES = ["ուն", "ներ", "ալ", "ել", "աւ", "էք", "էին", "ալու"]

TOKEN_RE = re.compile(r"[\u0531-\u058F]+")


def categorize_token(token: str) -> str:
    if token in PARTICLES:
        return "particle"
    # WA negative prefix forms such as չեմ, չես, չի, չենք, չեք, չեն, etc.
    if token.startswith("չ") and len(token) > 1:
        return "negative_prefix"
    if any(token.endswith(s) for s in MORPH_SUFFIXES):
        return "morphological_suffix"
    # spelling variants of WA 2nd person present
    if token.startswith("կու"):
        return "present_onset_gu"
    if token in {"մէջ", "տուն", "նոյն"}:
        return "dative_within"
    if token == "այլեւս":
        return "negative_conjunction"
    return "lexicon"


def main():
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    token_counts = Counter()

    for path in sorted(INPUT_DIR.glob("page_*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        tokens = TOKEN_RE.findall(text)
        token_counts.update(tokens)

    # Keep only tokens with 2+ occurrences for practical dictionary.
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["token", "count", "category"])
        writer.writeheader()
        for token, count in token_counts.most_common():
            category = categorize_token(token)
            writer.writerow({"token": token, "count": count, "category": category})

    print(f"Wrote lexicon to {OUTPUT_FILE} ({len(token_counts)} unique tokens)")


if __name__ == "__main__":
    main()
