#!/usr/bin/env python
"""Fetch corpora from Hugging Face Datasets and save per-language files for pairwise analysis.

This script attempts to load a dataset via the `datasets` library and extract text
sentences for a given language code (or language field). It writes a concatenated
text file to `analysis/external/{tag}/{tag}.txt` where tag is `ext:{lang}`.

Usage examples:
  python scripts/fetch_hf_datasets.py --dataset tatoeba --lang en --max-samples 50000
  python scripts/fetch_hf_datasets.py --dataset para_crawl --lang fr --split train
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import sys
from pathlib import Path as _Path
_scripts_dir = str(_Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from external_db import insert_external_record


def extract_texts_from_dataset(ds: Any, lang: str | None, max_samples: int) -> list[str]:
    texts = []
    for item in ds:
        if len(texts) >= max_samples:
            break
        # common patterns
        if isinstance(item, dict):
            # translation dicts
            if "translation" in item and isinstance(item["translation"], dict):
                # prefer requested lang
                if lang and lang in item["translation"]:
                    texts.append(item["translation"][lang])
                    continue
                # else take first value
                vals = list(item["translation"].values())
                if vals:
                    texts.append(vals[0])
                    continue

            # direct text fields
            for key in ("text", "sentence", "sent", "translation", "target"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    texts.append(v)
                    break

            # bilingual fields sometimes at top-level as mapping
            if isinstance(item.get("text"), dict) and lang and item.get("text").get(lang):
                texts.append(item["text"][lang])

    return texts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset name on Hugging Face (e.g., tatoeba)")
    parser.add_argument("--lang", required=True, help="Language code to extract (e.g., en, fr, ru)")
    parser.add_argument("--split", default="train", help="Split name to load (default: train)")
    parser.add_argument("--max-samples", type=int, default=50000, help="Max number of sentences to fetch")
    parser.add_argument("--outdir", default="analysis/external", help="Output base dir")
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except Exception:
        print("The 'datasets' library is required. Install with: pip install datasets")
        return

    ds = None
    # try a few loading patterns
    try:
        ds = load_dataset(args.dataset, split=args.split, trust_remote_code=True)
    except Exception:
        try:
            ds = load_dataset(args.dataset, args.lang, split=args.split, trust_remote_code=True)
        except Exception as exc:
            print("Failed to load dataset:", exc)
            return

    texts = extract_texts_from_dataset(ds, args.lang, args.max_samples)
    if not texts:
        print("No texts extracted from dataset. Try a different split or dataset.")
        return

    tag = f"ext:{args.lang}"
    # insert sentences into MongoDB as individual records
    inserted = 0
    batch = []
    for idx, t in enumerate(texts):
        try:
            insert_external_record(tag, f"{args.dataset}:{args.split}:{idx}", "hf_dataset_sentence", t, metadata={"dataset": args.dataset, "split": args.split, "lang": args.lang}, config_path="config/settings.yaml")
            inserted += 1
        except Exception:
            continue

    print(f"Inserted {inserted} sentences for tag {tag} into MongoDB")


if __name__ == "__main__":
    main()
