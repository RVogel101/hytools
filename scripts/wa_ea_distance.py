#!/usr/bin/env python
"""Compute WA vs EA distance metrics (phonetic, lexical, orthographic).

Lightweight, reproducible script producing CSV metrics and a manifest
in the `analysis/` directory. Uses existing hytools helpers.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Dict

from hytools.linguistics import get_phonetic_transcription, calculate_phonetic_difficulty
from hytools.ingestion._shared.helpers import get_lexical_markers
from hytools.linguistics.metrics.text_metrics import compute_orthographic_metrics


def compute_phonetic_distance(text_wa: str, text_ea: str) -> Dict:
    from nltk.metrics.distance import edit_distance
    t_wa_obj = get_phonetic_transcription(text_wa)
    t_ea_obj = get_phonetic_transcription(text_ea)

    # Extract IPA string if transcription returns a dict
    if isinstance(t_wa_obj, dict):
        t_wa = t_wa_obj.get("ipa", str(t_wa_obj))
    else:
        t_wa = str(t_wa_obj)

    if isinstance(t_ea_obj, dict):
        t_ea = t_ea_obj.get("ipa", str(t_ea_obj))
    else:
        t_ea = str(t_ea_obj)

    distance = edit_distance(t_wa, t_ea)
    difficulty_wa = calculate_phonetic_difficulty(text_wa)
    difficulty_ea = calculate_phonetic_difficulty(text_ea)
    return {
        "edit_distance": distance,
        "difficulty_wa": difficulty_wa,
        "difficulty_ea": difficulty_ea,
    }


def compute_lexical_distance(text_wa: str, text_ea: str) -> Dict:
    lexical_markers = get_lexical_markers()
    wa_count = sum(1 for marker, _ in lexical_markers if marker in text_wa)
    ea_count = sum(1 for marker, _ in lexical_markers if marker in text_ea)
    total = wa_count + ea_count
    wa_ratio = wa_count / total if total > 0 else 0.0
    return {"wa_count": wa_count, "ea_count": ea_count, "wa_ratio": wa_ratio}


def compute_orthographic_distance(text_wa: str, text_ea: str) -> Dict:
    o_wa = compute_orthographic_metrics(text_wa)
    o_ea = compute_orthographic_metrics(text_ea)
    return {
        "classical_markers_wa": o_wa.classical_markers_count,
        "reformed_markers_wa": o_wa.reformed_markers_count,
        "classical_to_reformed_ratio_wa": o_wa.classical_to_reformed_ratio,
        "classical_markers_ea": o_ea.classical_markers_count,
        "reformed_markers_ea": o_ea.reformed_markers_count,
        "classical_to_reformed_ratio_ea": o_ea.classical_to_reformed_ratio,
    }


def composite_index(phonetic: Dict, lexical: Dict, orthographic: Dict) -> float:
    weights = {"phonetic": 0.4, "lexical": 0.4, "orthographic": 0.2}
    p = phonetic.get("edit_distance", 0)
    l = lexical.get("wa_ratio", 0)
    o = (
        orthographic.get("classical_to_reformed_ratio_wa", 0)
        + orthographic.get("classical_to_reformed_ratio_ea", 0)
    ) / 2
    return weights["phonetic"] * p + weights["lexical"] * l + weights["orthographic"] * o

def compute_all_metrics_for_texts(wa_text: str, ea_text: str):
    phon = compute_phonetic_distance(wa_text, ea_text)
    lex = compute_lexical_distance(wa_text, ea_text)
    orth = compute_orthographic_distance(wa_text, ea_text)
    comp = composite_index(phon, lex, orth)
    return {"phonetic": phon, "lexical": lex, "orthographic": orth, "composite": comp}


def write_csv(out_path: str, row: Dict, fieldnames: list[str]):
    first = not os.path.exists(out_path)
    with open(out_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if first:
            w.writeheader()
        w.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="WA vs EA distance analysis")
    parser.add_argument("--wa", required=True, help="Path to Western Armenian text file")
    parser.add_argument("--ea", required=True, help="Path to Eastern Armenian text file")
    parser.add_argument("--outdir", default="analysis", help="Output directory for CSVs")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    wa_text = open(args.wa, "r", encoding="utf-8").read()
    ea_text = open(args.ea, "r", encoding="utf-8").read()

    phon = compute_phonetic_distance(wa_text, ea_text)
    lex = compute_lexical_distance(wa_text, ea_text)
    orth = compute_orthographic_distance(wa_text, ea_text)

    comp = composite_index(phon, lex, orth)

    # Write outputs
    write_csv(os.path.join(args.outdir, "wa_ea_phonetic_metrics.csv"), phon, ["edit_distance", "difficulty_wa", "difficulty_ea"])
    write_csv(os.path.join(args.outdir, "wa_ea_lexical_metrics.csv"), lex, ["wa_count", "ea_count", "wa_ratio"])
    write_csv(os.path.join(args.outdir, "wa_ea_orthographic_metrics.csv"), orth, [
        "classical_markers_wa",
        "reformed_markers_wa",
        "classical_to_reformed_ratio_wa",
        "classical_markers_ea",
        "reformed_markers_ea",
        "classical_to_reformed_ratio_ea",
    ])

    write_csv(os.path.join(args.outdir, "wa_ea_distance_index.csv"), {"composite_distance_index": comp}, ["composite_distance_index"])

    # Update manifest minimally
    manifest_path = os.path.join(args.outdir, "wa_ea_corpus_manifest.json")
    manifest = {"wa_file": args.wa, "ea_file": args.ea, "composite_index": comp}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("Analysis complete. Outputs in:", args.outdir)


if __name__ == "__main__":
    main()
