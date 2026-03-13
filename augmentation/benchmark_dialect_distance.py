"""Benchmark dialect distance models on WA/EA corpora.

Compares multiple metric configurations and reports how well they separate:
- intra-dialect pairs (WA vs WA, EA vs EA)
- inter-dialect pairs (WA vs EA)

Higher separation margin (inter - intra) is better.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from linguistics.dialect.dialect_distance import (
    DistanceWeights,
    compute_component_distance,
)


def _read_texts(dirs: list[str], max_files: int = 2000, seed: int = 42) -> list[str]:
    rng = random.Random(seed)
    files: list[Path] = []
    for d in dirs:
        p = Path(d)
        if not p.exists():
            continue
        files.extend(sorted(p.rglob("*.txt")))

    if len(files) > max_files:
        files = rng.sample(files, max_files)

    texts: list[str] = []
    for f in files:
        try:
            texts.append(f.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
    return texts


def _split_half(items: list[str], rng: random.Random) -> tuple[list[str], list[str]]:
    items = items[:]
    rng.shuffle(items)
    mid = max(1, len(items) // 2)
    return items[:mid], items[mid:] if mid < len(items) else items[:mid]


def _score_config(
    wa_texts: list[str],
    ea_texts: list[str],
    weights: DistanceWeights,
    mapping: dict[str, dict],
    variant_pairs: list[tuple[str, str]],
    contextual_keywords: list[str],
    function_words: set[str],
    trials: int,
    seed: int,
) -> dict[str, float]:
    rng = random.Random(seed)

    intra_scores: list[float] = []
    inter_scores: list[float] = []

    for _ in range(trials):
        wa_a, wa_b = _split_half(wa_texts, rng)
        ea_a, ea_b = _split_half(ea_texts, rng)

        wa_intra = compute_component_distance(
            wa_a,
            wa_b,
            west_east_mapping=mapping,
            variant_pairs=variant_pairs,
            contextual_keywords=contextual_keywords,
            function_words=function_words,
            weights=weights,
        ).total_distance
        ea_intra = compute_component_distance(
            ea_a,
            ea_b,
            west_east_mapping=mapping,
            variant_pairs=variant_pairs,
            contextual_keywords=contextual_keywords,
            function_words=function_words,
            weights=weights,
        ).total_distance

        inter = compute_component_distance(
            wa_a,
            ea_a,
            west_east_mapping=mapping,
            variant_pairs=variant_pairs,
            contextual_keywords=contextual_keywords,
            function_words=function_words,
            weights=weights,
        ).total_distance

        intra_scores.append((wa_intra + ea_intra) / 2.0)
        inter_scores.append(inter)

    avg_intra = sum(intra_scores) / max(len(intra_scores), 1)
    avg_inter = sum(inter_scores) / max(len(inter_scores), 1)
    margin = avg_inter - avg_intra

    return {
        "avg_intra_distance": avg_intra,
        "avg_inter_distance": avg_inter,
        "separation_margin": margin,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m augmentation.benchmark_dialect_distance",
        description="Benchmark WA/EA distance metric configurations.",
    )
    parser.add_argument(
        "--wa-dirs",
        nargs="+",
        required=True,
        help="Western Armenian corpus directories",
    )
    parser.add_argument(
        "--ea-dirs",
        nargs="+",
        required=True,
        help="Eastern Armenian corpus directories",
    )
    parser.add_argument("--mapping", default="cache/west_east_usage_mapping.json")
    parser.add_argument(
        "--variant-pairs-json",
        default="",
        help="Optional JSON file with explicit variant pairs: [[western,eastern], ...]",
    )
    parser.add_argument(
        "--contextual-keywords-json",
        default="",
        help="Optional JSON file with shared keywords for context divergence: [word1, word2, ...]",
    )
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="cache/dialect_distance_benchmark.json")
    args = parser.parse_args()

    wa_texts = _read_texts(args.wa_dirs, max_files=args.max_files, seed=args.seed)
    ea_texts = _read_texts(args.ea_dirs, max_files=args.max_files, seed=args.seed + 1)

    if len(wa_texts) < 2 or len(ea_texts) < 2:
        raise SystemExit("Need at least 2 WA texts and 2 EA texts for benchmarking.")

    mapping_path = Path(args.mapping)
    mapping: dict[str, dict] = {}
    if mapping_path.exists():
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    variant_pairs = [
        (str(meta.get("canonical_western_form", "")).strip(), ea)
        for ea, meta in mapping.items()
        if str(meta.get("canonical_western_form", "")).strip()
    ]

    if args.variant_pairs_json:
        vp_path = Path(args.variant_pairs_json)
        if vp_path.exists():
            raw_pairs = json.loads(vp_path.read_text(encoding="utf-8"))
            for pair in raw_pairs:
                if isinstance(pair, list) and len(pair) == 2:
                    west_form = str(pair[0]).strip()
                    east_form = str(pair[1]).strip()
                    if west_form and east_form:
                        variant_pairs.append((west_form, east_form))

    # Dedupe while preserving order.
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for p in variant_pairs:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    variant_pairs = deduped

    # Minimal WA function-word seed. Extend this from corpus stats later.
    function_words = {
        "կը",
        "պիտի",
        "հոն",
        "հոս",
        "ու",
        "ալ",
        "որ",
        "չեմ",
        "չէ",
    }

    contextual_keywords: list[str] = []
    if args.contextual_keywords_json:
        ck_path = Path(args.contextual_keywords_json)
        if ck_path.exists():
            raw_keywords = json.loads(ck_path.read_text(encoding="utf-8"))
            contextual_keywords = [str(w).strip() for w in raw_keywords if str(w).strip()]

    configs: dict[str, DistanceWeights] = {
        "lexical_js_only": DistanceWeights(
            lexical_weight=1.0,
            structural_weight=0.0,
            lexical_subweights={
                "js_divergence": 1.0,
                "weighted_jaccard_distance": 0.0,
                "mapping_shift_rate": 0.0,
                "variant_usage_rate_distance": 0.0,
                "keyword_context_js": 0.0,
            },
            structural_subweights={
                "sentence_length_wasserstein": 1.0,
                "function_bigram_js": 0.0,
            },
        ),
        "lexical_full": DistanceWeights(
            lexical_weight=1.0,
            structural_weight=0.0,
        ),
        "structure_only": DistanceWeights(
            lexical_weight=0.0,
            structural_weight=1.0,
        ),
        "component_default": DistanceWeights(),
        "component_usage_heavy": DistanceWeights(
            lexical_weight=0.7,
            structural_weight=0.3,
            lexical_subweights={
                "js_divergence": 0.30,
                "weighted_jaccard_distance": 0.20,
                "mapping_shift_rate": 0.15,
                "variant_usage_rate_distance": 0.35,
                "keyword_context_js": 0.0,
            },
            structural_subweights={
                "sentence_length_wasserstein": 0.60,
                "function_bigram_js": 0.40,
            },
        ),
    }

    results: dict[str, dict] = {}
    for name, cfg in configs.items():
        results[name] = _score_config(
            wa_texts,
            ea_texts,
            cfg,
            mapping,
            variant_pairs,
            contextual_keywords,
            function_words,
            trials=args.trials,
            seed=args.seed,
        )

    ranked = sorted(results.items(), key=lambda kv: kv[1]["separation_margin"], reverse=True)

    payload = {
        "meta": {
            "wa_docs": len(wa_texts),
            "ea_docs": len(ea_texts),
            "trials": args.trials,
            "mapping_pairs": len(variant_pairs),
            "contextual_keywords": len(contextual_keywords),
        },
        "results": results,
        "ranking": [name for name, _ in ranked],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Dialect distance benchmark completed.")
    print(f"Output: {out_path}")
    print("Ranking by separation margin:")
    for idx, (name, score) in enumerate(ranked, start=1):
        print(
            f"  {idx}. {name}: margin={score['separation_margin']:.4f} "
            f"(inter={score['avg_inter_distance']:.4f}, intra={score['avg_intra_distance']:.4f})"
        )


if __name__ == "__main__":
    main()
