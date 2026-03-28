#!/usr/bin/env python
"""Import external benchmark datasets (ASJP/CSV) and normalize distances.

Usage:
  python scripts/import_benchmarks.py --csv path/to/benchmarks.csv

The script expects a CSV with at least two columns: `pair` and `distance`.
It writes normalized distances to `analysis/wa_ea_benchmark_comparison.csv`.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from typing import List, Tuple


def read_csv(path: str) -> List[Tuple[str, float]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for rec in r:
            pair = rec.get("pair") or rec.get("language_pair") or rec.get("pair_name")
            dist = rec.get("distance") or rec.get("d") or rec.get("value")
            if pair is None or dist is None:
                continue
            try:
                val = float(dist)
            except Exception:
                continue
            rows.append((pair, val))
    return rows


def normalize(rows: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    if not rows:
        return []
    vals = [v for (_, v) in rows]
    mn = min(vals)
    mx = max(vals)
    if math.isclose(mx, mn):
        return [(p, 0.0) for (p, _) in rows]
    out = [(p, (v - mn) / (mx - mn)) for (p, v) in rows]
    return out


def append_to_benchmark_csv(out_path: str, rows: List[Tuple[str, float]]):
    first = not os.path.exists(out_path)
    with open(out_path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if first:
            w.writerow(["pair", "normalized_distance", "source"])
        for pair, nd in rows:
            w.writerow([pair, f"{nd:.6f}", "imported"])


def main():
    parser = argparse.ArgumentParser(description="Import benchmark CSV and normalize distances")
    parser.add_argument("--csv", help="Path to benchmark CSV file")
    parser.add_argument("--out", default="analysis/wa_ea_benchmark_comparison.csv", help="Output benchmark CSV")
    args = parser.parse_args()

    rows = read_csv(args.csv)
    if not rows:
        print("No valid rows found in", args.csv)
        return
    norm = normalize(rows)
    append_to_benchmark_csv(args.out, norm)
    print(f"Imported {len(norm)} benchmark rows into {args.out}")


if __name__ == "__main__":
    main()
