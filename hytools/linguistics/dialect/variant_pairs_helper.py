"""Utilities to bootstrap high-impact WA/EA variant pairs.

Generates a starter ``variant_pairs.json`` (format: ``[[west,east], ...]``)
from the corpus-grounded West-East mapping so benchmark/calibration runs can
quickly include strong lexical alternations.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _pair_impact_score(metadata: dict) -> float:
    """Compute a simple impact score for ranking mapping-derived pairs."""
    west_freq = int(metadata.get("canonical_western_frequency_in_wa", 0) or 0)
    east_freq = int(metadata.get("eastern_frequency_in_wa", 0) or 0)
    support = west_freq + east_freq
    if support <= 0:
        return 0.0

    # Prefer pairs that are common and strongly WA-dominant in WA corpora.
    dominance = float(metadata.get("canonical_western_dominance_ratio", 0.0) or 0.0)
    return math.log1p(support) * max(dominance, 0.0)


def build_starter_variant_pairs(
    mapping: dict[str, dict],
    *,
    top_k: int = 40,
    min_support: int = 2,
    min_dominance: float = 0.60,
    min_frequency_delta: int = 1,
) -> list[tuple[str, str]]:
    """Create a ranked starter list of ``(western_form, eastern_form)`` pairs."""
    ranked: list[tuple[float, str, str]] = []

    for eastern_form, metadata in mapping.items():
        western_form = str(metadata.get("canonical_western_form", "")).strip()
        if not western_form:
            continue

        west_freq = int(metadata.get("canonical_western_frequency_in_wa", 0) or 0)
        east_freq = int(metadata.get("eastern_frequency_in_wa", 0) or 0)
        support = west_freq + east_freq
        dominance = float(metadata.get("canonical_western_dominance_ratio", 0.0) or 0.0)
        freq_delta = int(metadata.get("canonical_frequency_delta", west_freq - east_freq) or 0)

        if support < min_support:
            continue
        if dominance < min_dominance:
            continue
        if freq_delta < min_frequency_delta:
            continue

        score = _pair_impact_score(metadata)
        if score <= 0.0:
            continue
        ranked.append((score, western_form, str(eastern_form).strip()))

    ranked.sort(key=lambda row: row[0], reverse=True)

    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, west, east in ranked:
        pair = (west, east)
        if pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
        if len(out) >= top_k:
            break

    return out


def save_variant_pairs_json(pairs: list[tuple[str, str]], output_path: str | Path) -> Path:
    """Persist pairs as JSON list-of-lists accepted by benchmark/calibration CLIs."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [[west, east] for west, east in pairs]
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m linguistics.dialect.variant_pairs_helper",
        description="Generate starter variant_pairs.json from West-East usage mapping.",
    )
    parser.add_argument("--mapping", default="cache/west_east_usage_mapping.json")
    parser.add_argument("--out", default="cache/variant_pairs_starter.json")
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--min-dominance", type=float, default=0.60)
    parser.add_argument("--min-frequency-delta", type=int, default=1)
    args = parser.parse_args()

    mapping_path = Path(args.mapping)
    if not mapping_path.exists():
        raise SystemExit(
            "Mapping file not found. Run corpus_vocabulary_builder first, "
            "or pass --mapping <path>."
        )

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise SystemExit("Mapping JSON must be an object keyed by Eastern form.")

    pairs = build_starter_variant_pairs(
        mapping,
        top_k=max(args.top_k, 1),
        min_support=max(args.min_support, 0),
        min_dominance=max(min(args.min_dominance, 1.0), 0.0),
        min_frequency_delta=max(args.min_frequency_delta, 0),
    )
    out_path = save_variant_pairs_json(pairs, args.out)

    print(f"Generated {len(pairs)} starter variant pairs.")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
